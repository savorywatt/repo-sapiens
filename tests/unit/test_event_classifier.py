"""Unit tests for event classifier module."""

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import (
    AutomationConfig,
    AutomationModeConfig,
    LabelTriggerConfig,
    TriggerType,
)
from repo_sapiens.engine.event_classifier import (
    ClassifiedEvent,
    EventClassifier,
    EventSource,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock automation settings with label triggers configured."""
    return AutomationSettings(
        git_provider={
            "provider_type": "gitea",
            "base_url": "https://gitea.example.com",
            "api_token": "test-token",
        },
        repository={
            "owner": "test-owner",
            "name": "test-repo",
        },
        agent_provider={
            "provider_type": "claude-local",
            "model": "claude-3-sonnet",
        },
        automation=AutomationConfig(
            mode=AutomationModeConfig(
                mode="hybrid",
                native_enabled=True,
                daemon_enabled=True,
            ),
            label_triggers={
                "sapiens/triage": LabelTriggerConfig(
                    label_pattern="sapiens/triage",
                    handler="triage",
                    ai_enabled=True,
                    remove_on_complete=True,
                    success_label="triaged",
                ),
                "needs-planning": LabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                    ai_enabled=True,
                    remove_on_complete=True,
                    success_label="proposed",
                ),
                "sapiens/*": LabelTriggerConfig(
                    label_pattern="sapiens/*",
                    handler="generic",
                    ai_enabled=True,
                ),
            },
        ),
    )


@pytest.fixture
def mock_settings_native_disabled(tmp_path):
    """Create settings with native triggers disabled."""
    return AutomationSettings(
        git_provider={
            "provider_type": "github",
            "base_url": "https://api.github.com",
            "api_token": "test-token",
        },
        repository={
            "owner": "test-owner",
            "name": "test-repo",
        },
        agent_provider={
            "provider_type": "claude-local",
            "model": "claude-3-sonnet",
        },
        automation=AutomationConfig(
            mode=AutomationModeConfig(
                mode="daemon",
                native_enabled=False,
                daemon_enabled=True,
            ),
            label_triggers={
                "needs-planning": LabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                ),
            },
        ),
    )


class TestEventSource:
    """Tests for EventSource enum."""

    def test_event_source_values(self):
        """Test EventSource enum values."""
        assert EventSource.GITEA.value == "gitea"
        assert EventSource.GITHUB.value == "github"
        assert EventSource.GITLAB.value == "gitlab"

    def test_event_source_from_string(self):
        """Test creating EventSource from string."""
        assert EventSource("gitea") == EventSource.GITEA
        assert EventSource("github") == EventSource.GITHUB
        assert EventSource("gitlab") == EventSource.GITLAB


class TestClassifiedEvent:
    """Tests for ClassifiedEvent dataclass."""

    def test_classified_event_creation(self):
        """Test creating a ClassifiedEvent instance."""
        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITEA,
            handler="triage",
            config=None,
            issue_number=42,
            pr_number=None,
            label="sapiens/triage",
            raw_event={"action": "labeled"},
            should_process=True,
            skip_reason=None,
        )

        assert event.trigger_type == TriggerType.LABEL_ADDED
        assert event.source == EventSource.GITEA
        assert event.handler == "triage"
        assert event.issue_number == 42
        assert event.pr_number is None
        assert event.label == "sapiens/triage"
        assert event.should_process is True

    def test_classified_event_skip(self):
        """Test ClassifiedEvent with skip reason."""
        event = ClassifiedEvent(
            trigger_type=TriggerType.MANUAL,
            source=EventSource.GITHUB,
            handler=None,
            config=None,
            issue_number=None,
            pr_number=None,
            label=None,
            raw_event={},
            should_process=False,
            skip_reason="Unknown event type",
        )

        assert event.should_process is False
        assert event.skip_reason == "Unknown event type"


class TestEventClassifier:
    """Tests for EventClassifier class."""

    def test_classifier_initialization(self, mock_settings):
        """Test EventClassifier initialization."""
        classifier = EventClassifier(mock_settings)

        assert classifier.settings == mock_settings
        assert classifier.automation == mock_settings.automation
        assert isinstance(classifier._label_cache, dict)

    def test_classify_label_added_gitea(self, mock_settings):
        """Test classifying a Gitea label added event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "sapiens/triage"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.LABEL_ADDED
        assert result.source == EventSource.GITEA
        assert result.handler == "triage"
        assert result.label == "sapiens/triage"
        assert result.issue_number == 42
        assert result.should_process is True

    def test_classify_label_added_github(self, mock_settings):
        """Test classifying a GitHub label added event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "needs-planning"},
            "issue": {"number": 123},
        }

        result = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.LABEL_ADDED
        assert result.source == EventSource.GITHUB
        assert result.handler == "proposal"
        assert result.label == "needs-planning"
        assert result.issue_number == 123
        assert result.should_process is True

    def test_classify_label_removed(self, mock_settings):
        """Test classifying a label removed event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "unlabeled",
            "label": {"name": "needs-planning"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.unlabeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.LABEL_REMOVED
        # Label removal typically doesn't trigger handlers
        assert result.handler == "proposal"  # Still finds the config

    def test_classify_unknown_label(self, mock_settings):
        """Test classifying an event with an unknown label."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "unknown-label"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.LABEL_ADDED
        assert result.handler is None
        assert result.should_process is False
        assert "No handler configured" in result.skip_reason

    def test_classify_glob_pattern_match(self, mock_settings):
        """Test classifying with glob pattern matching."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "sapiens/review/security"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.LABEL_ADDED
        assert result.handler == "generic"  # Matches sapiens/* pattern
        assert result.should_process is True

    def test_classify_unknown_event_type(self, mock_settings):
        """Test classifying an unknown event type."""
        classifier = EventClassifier(mock_settings)

        event_data = {"action": "unknown"}

        result = classifier.classify(
            event_type="unknown.event",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.MANUAL  # Default
        assert result.should_process is False
        assert "Unknown event type" in result.skip_reason

    def test_classify_native_disabled(self, mock_settings_native_disabled):
        """Test classifying when native triggers are disabled."""
        classifier = EventClassifier(mock_settings_native_disabled)

        event_data = {
            "action": "labeled",
            "label": {"name": "needs-planning"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.should_process is False
        assert "Native triggers disabled" in result.skip_reason

    def test_classify_pr_event(self, mock_settings):
        """Test classifying a PR label event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "needs-planning"},
            "pull_request": {"number": 99},
        }

        result = classifier.classify(
            event_type="pull_request.labeled",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.LABEL_ADDED
        assert result.pr_number == 99
        assert result.issue_number is None

    def test_classify_issue_opened(self, mock_settings):
        """Test classifying an issue opened event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "opened",
            "issue": {"number": 42, "title": "New issue"},
        }

        result = classifier.classify(
            event_type="issues.opened",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.ISSUE_OPENED
        assert result.issue_number == 42

    def test_classify_issue_closed(self, mock_settings):
        """Test classifying an issue closed event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "closed",
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issues.closed",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.ISSUE_CLOSED

    def test_classify_pr_opened(self, mock_settings):
        """Test classifying a PR opened event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "opened",
            "pull_request": {"number": 50},
        }

        result = classifier.classify(
            event_type="pull_request.opened",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.PR_OPENED
        assert result.pr_number == 50

    def test_classify_pr_merged(self, mock_settings):
        """Test classifying a PR merged event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "closed",
            "pull_request": {"number": 50, "merged": True},
        }

        result = classifier.classify(
            event_type="pull_request.closed",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.PR_MERGED

    def test_classify_pr_closed_not_merged(self, mock_settings):
        """Test classifying a PR closed but not merged."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "closed",
            "pull_request": {"number": 50, "merged": False},
        }

        result = classifier.classify(
            event_type="pull_request.closed",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.PR_CLOSED

    def test_classify_push_event(self, mock_settings):
        """Test classifying a push event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "ref": "refs/heads/main",
            "commits": [],
        }

        result = classifier.classify(
            event_type="push",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result.trigger_type == TriggerType.PUSH

    def test_classify_schedule_event(self, mock_settings):
        """Test classifying a schedule event."""
        classifier = EventClassifier(mock_settings)

        event_data = {}

        result = classifier.classify(
            event_type="schedule",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.SCHEDULE

    def test_classify_workflow_dispatch(self, mock_settings):
        """Test classifying a workflow dispatch event."""
        classifier = EventClassifier(mock_settings)

        event_data = {"inputs": {}}

        result = classifier.classify(
            event_type="workflow_dispatch",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.MANUAL

    def test_classify_comment_event(self, mock_settings):
        """Test classifying a comment event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "created",
            "comment": {"body": "Test comment"},
            "issue": {"number": 42},
        }

        result = classifier.classify(
            event_type="issue_comment.created",
            event_data=event_data,
            source=EventSource.GITHUB,
        )

        assert result.trigger_type == TriggerType.COMMENT

    def test_label_cache(self, mock_settings):
        """Test that label matching results are cached."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "action": "labeled",
            "label": {"name": "sapiens/triage"},
            "issue": {"number": 42},
        }

        # First classification - cache miss
        result1 = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert "sapiens/triage" in classifier._label_cache

        # Second classification - cache hit
        result2 = classifier.classify(
            event_type="issues.labeled",
            event_data=event_data,
            source=EventSource.GITEA,
        )

        assert result1.handler == result2.handler

    def test_extract_gitlab_label(self, mock_settings):
        """Test extracting labels from GitLab event format."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "changes": {
                "labels": {
                    "current": [{"title": "needs-planning"}],
                    "previous": [],
                }
            },
            "object_attributes": {"iid": 42},
        }

        result = classifier.classify(
            event_type="Issue Hook",
            event_data=event_data,
            source=EventSource.GITLAB,
        )

        # GitLab "Issue Hook" won't match standard event patterns directly
        # This tests the label extraction mechanism
        assert result.issue_number == 42

    def test_extract_gitlab_mr_number(self, mock_settings):
        """Test extracting MR number from GitLab event."""
        classifier = EventClassifier(mock_settings)

        event_data = {
            "merge_request": {"iid": 55},
        }

        result = classifier.classify(
            event_type="merge_request.opened",
            event_data=event_data,
            source=EventSource.GITLAB,
        )

        assert result.pr_number == 55


class TestDetermineTrigerType:
    """Tests for _determine_trigger_type method."""

    def test_various_labeled_formats(self, mock_settings):
        """Test various formats of labeled event types."""
        classifier = EventClassifier(mock_settings)

        # Test different casing
        assert (
            classifier._determine_trigger_type("issues.labeled", {}, EventSource.GITEA)
            == TriggerType.LABEL_ADDED
        )

        assert (
            classifier._determine_trigger_type("Issues.Labeled", {}, EventSource.GITHUB)
            == TriggerType.LABEL_ADDED
        )

        assert (
            classifier._determine_trigger_type("ISSUES.LABELED", {}, EventSource.GITEA)
            == TriggerType.LABEL_ADDED
        )

    def test_unlabeled_takes_precedence(self, mock_settings):
        """Test that unlabeled is detected even if 'labeled' is in the string."""
        classifier = EventClassifier(mock_settings)

        assert (
            classifier._determine_trigger_type("issues.unlabeled", {}, EventSource.GITEA)
            == TriggerType.LABEL_REMOVED
        )


class TestFindHandler:
    """Tests for _find_handler method."""

    def test_exact_match(self, mock_settings):
        """Test exact label match."""
        classifier = EventClassifier(mock_settings)

        handler, config = classifier._find_handler(TriggerType.LABEL_ADDED, "sapiens/triage")

        assert handler == "triage"
        assert config is not None
        assert config.handler == "triage"

    def test_glob_match(self, mock_settings):
        """Test glob pattern match."""
        classifier = EventClassifier(mock_settings)

        handler, config = classifier._find_handler(TriggerType.LABEL_ADDED, "sapiens/any/path")

        assert handler == "generic"

    def test_no_match(self, mock_settings):
        """Test no matching pattern."""
        classifier = EventClassifier(mock_settings)

        handler, config = classifier._find_handler(TriggerType.LABEL_ADDED, "unknown")

        assert handler is None
        assert config is None

    def test_non_label_trigger(self, mock_settings):
        """Test non-label triggers return None."""
        classifier = EventClassifier(mock_settings)

        handler, config = classifier._find_handler(TriggerType.PUSH, None)

        assert handler is None
        assert config is None
