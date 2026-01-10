"""Tests for repo_sapiens/config/triggers.py Pydantic models.

Tests cover:
- TriggerType enum values
- LabelTriggerConfig validation
- ScheduleTriggerConfig validation
- AutomationModeConfig defaults and validation
- AutomationConfig composition
- PROVIDER_EVENT_MAP structure
- Backward compatibility (configs without automation field)
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from repo_sapiens.config.triggers import (
    PROVIDER_EVENT_MAP,
    AutomationConfig,
    AutomationModeConfig,
    LabelTriggerConfig,
    ScheduleTriggerConfig,
    TriggerType,
)


class TestTriggerType:
    """Test TriggerType enum values and behavior."""

    def test_all_trigger_types_exist(self):
        """Test all expected trigger types are defined."""
        expected_types = [
            "label_added",
            "label_removed",
            "issue_opened",
            "issue_closed",
            "pr_opened",
            "pr_merged",
            "pr_closed",
            "push",
            "schedule",
            "manual",
            "comment",
        ]

        for type_name in expected_types:
            assert hasattr(TriggerType, type_name.upper())

    def test_trigger_type_values(self):
        """Test trigger type enum values are strings."""
        assert TriggerType.LABEL_ADDED.value == "label_added"
        assert TriggerType.PR_MERGED.value == "pr_merged"
        assert TriggerType.SCHEDULE.value == "schedule"

    def test_trigger_type_is_string_enum(self):
        """Test TriggerType inherits from str."""
        assert isinstance(TriggerType.LABEL_ADDED, str)
        assert TriggerType.LABEL_ADDED == "label_added"

    def test_trigger_type_from_string(self):
        """Test creating TriggerType from string value."""
        trigger = TriggerType("label_added")
        assert trigger == TriggerType.LABEL_ADDED

    def test_invalid_trigger_type_raises_error(self):
        """Test invalid trigger type raises ValueError."""
        with pytest.raises(ValueError):
            TriggerType("invalid_type")


class TestLabelTriggerConfig:
    """Test LabelTriggerConfig validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid label trigger configuration."""
        config = LabelTriggerConfig(
            label_pattern="needs-planning",
            handler="proposal",
        )

        assert config.label_pattern == "needs-planning"
        assert config.handler == "proposal"

    def test_default_values(self):
        """Test default values are correctly set."""
        config = LabelTriggerConfig(
            label_pattern="test-label",
            handler="test-handler",
        )

        assert config.ai_enabled is True
        assert config.remove_on_complete is True
        assert config.success_label is None
        assert config.failure_label == "needs-attention"

    def test_glob_pattern_in_label(self):
        """Test glob patterns are accepted in label_pattern."""
        config = LabelTriggerConfig(
            label_pattern="sapiens/*",
            handler="auto-handler",
        )

        assert config.label_pattern == "sapiens/*"

    def test_custom_success_and_failure_labels(self):
        """Test custom success and failure labels."""
        config = LabelTriggerConfig(
            label_pattern="needs-review",
            handler="review",
            success_label="reviewed",
            failure_label="review-failed",
        )

        assert config.success_label == "reviewed"
        assert config.failure_label == "review-failed"

    def test_ai_disabled(self):
        """Test ai_enabled can be set to False."""
        config = LabelTriggerConfig(
            label_pattern="simple-task",
            handler="simple",
            ai_enabled=False,
        )

        assert config.ai_enabled is False

    def test_remove_on_complete_disabled(self):
        """Test remove_on_complete can be set to False."""
        config = LabelTriggerConfig(
            label_pattern="persistent-label",
            handler="handler",
            remove_on_complete=False,
        )

        assert config.remove_on_complete is False

    def test_missing_label_pattern_raises_error(self):
        """Test missing label_pattern raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LabelTriggerConfig(handler="handler")

        assert "label_pattern" in str(exc_info.value).lower()

    def test_missing_handler_raises_error(self):
        """Test missing handler raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LabelTriggerConfig(label_pattern="label")

        assert "handler" in str(exc_info.value).lower()

    def test_none_failure_label(self):
        """Test failure_label can be explicitly set to None."""
        config = LabelTriggerConfig(
            label_pattern="test",
            handler="handler",
            failure_label=None,
        )

        assert config.failure_label is None


class TestScheduleTriggerConfig:
    """Test ScheduleTriggerConfig validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid schedule trigger configuration."""
        config = ScheduleTriggerConfig(
            cron="0 8 * * 1-5",
            handler="daily_triage",
        )

        assert config.cron == "0 8 * * 1-5"
        assert config.handler == "daily_triage"

    def test_default_values(self):
        """Test default values are correctly set."""
        config = ScheduleTriggerConfig(
            cron="0 0 * * *",
            handler="nightly",
        )

        assert config.task_prompt is None
        assert config.ai_enabled is True

    def test_with_task_prompt(self):
        """Test schedule with custom task prompt."""
        config = ScheduleTriggerConfig(
            cron="0 9 * * 1",
            handler="weekly_review",
            task_prompt="Review all open issues and prioritize for the week",
        )

        assert config.task_prompt == "Review all open issues and prioritize for the week"

    def test_ai_disabled(self):
        """Test ai_enabled can be set to False."""
        config = ScheduleTriggerConfig(
            cron="*/5 * * * *",
            handler="health_check",
            ai_enabled=False,
        )

        assert config.ai_enabled is False

    def test_missing_cron_raises_error(self):
        """Test missing cron raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleTriggerConfig(handler="handler")

        assert "cron" in str(exc_info.value).lower()

    def test_missing_handler_raises_error(self):
        """Test missing handler raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleTriggerConfig(cron="0 0 * * *")

        assert "handler" in str(exc_info.value).lower()

    def test_various_cron_expressions(self):
        """Test various valid cron expressions are accepted."""
        cron_expressions = [
            "0 0 * * *",  # Daily at midnight
            "*/15 * * * *",  # Every 15 minutes
            "0 8 * * 1-5",  # Weekdays at 8am
            "0 0 1 * *",  # Monthly on the 1st
            "0 12 * * 0",  # Sundays at noon
        ]

        for cron in cron_expressions:
            config = ScheduleTriggerConfig(cron=cron, handler="test")
            assert config.cron == cron


class TestAutomationModeConfig:
    """Test AutomationModeConfig validation and defaults."""

    def test_default_values(self):
        """Test all default values are correctly set."""
        config = AutomationModeConfig()

        assert config.mode == "hybrid"
        assert config.native_enabled is True
        assert config.daemon_enabled is True
        assert config.daemon_fallback_only is True
        assert config.label_prefix == "sapiens/"

    def test_native_mode(self):
        """Test native-only mode configuration."""
        config = AutomationModeConfig(
            mode="native",
            native_enabled=True,
            daemon_enabled=False,
        )

        assert config.mode == "native"
        assert config.native_enabled is True
        assert config.daemon_enabled is False

    def test_daemon_mode(self):
        """Test daemon-only mode configuration."""
        config = AutomationModeConfig(
            mode="daemon",
            native_enabled=False,
            daemon_enabled=True,
        )

        assert config.mode == "daemon"
        assert config.native_enabled is False
        assert config.daemon_enabled is True

    def test_hybrid_mode(self):
        """Test hybrid mode configuration."""
        config = AutomationModeConfig(
            mode="hybrid",
            native_enabled=True,
            daemon_enabled=True,
            daemon_fallback_only=False,
        )

        assert config.mode == "hybrid"
        assert config.daemon_fallback_only is False

    def test_custom_label_prefix(self):
        """Test custom label prefix."""
        config = AutomationModeConfig(label_prefix="automation/")

        assert config.label_prefix == "automation/"

    def test_invalid_mode_raises_error(self):
        """Test invalid mode value raises validation error."""
        with pytest.raises(ValidationError):
            AutomationModeConfig(mode="invalid")

    def test_valid_mode_values(self):
        """Test all valid mode values are accepted."""
        for mode in ["native", "daemon", "hybrid"]:
            config = AutomationModeConfig(mode=mode)
            assert config.mode == mode


class TestAutomationConfig:
    """Test AutomationConfig composition and defaults."""

    def test_default_values(self):
        """Test all default values are correctly set."""
        config = AutomationConfig()

        assert isinstance(config.mode, AutomationModeConfig)
        assert config.label_triggers == {}
        assert config.schedule_triggers == []

    def test_with_label_triggers(self):
        """Test AutomationConfig with label triggers."""
        config = AutomationConfig(
            label_triggers={
                "sapiens/triage": LabelTriggerConfig(
                    label_pattern="sapiens/triage",
                    handler="triage",
                ),
                "needs-planning": LabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                ),
            }
        )

        assert len(config.label_triggers) == 2
        assert "sapiens/triage" in config.label_triggers
        assert config.label_triggers["sapiens/triage"].handler == "triage"

    def test_with_schedule_triggers(self):
        """Test AutomationConfig with schedule triggers."""
        config = AutomationConfig(
            schedule_triggers=[
                ScheduleTriggerConfig(cron="0 8 * * 1-5", handler="daily"),
                ScheduleTriggerConfig(cron="0 0 * * 0", handler="weekly"),
            ]
        )

        assert len(config.schedule_triggers) == 2
        assert config.schedule_triggers[0].handler == "daily"
        assert config.schedule_triggers[1].handler == "weekly"

    def test_with_custom_mode(self):
        """Test AutomationConfig with custom mode configuration."""
        config = AutomationConfig(
            mode=AutomationModeConfig(
                mode="native",
                daemon_enabled=False,
            )
        )

        assert config.mode.mode == "native"
        assert config.mode.daemon_enabled is False

    def test_complete_configuration(self):
        """Test complete automation configuration."""
        config = AutomationConfig(
            mode=AutomationModeConfig(
                mode="hybrid",
                label_prefix="auto/",
            ),
            label_triggers={
                "auto/review": LabelTriggerConfig(
                    label_pattern="auto/review",
                    handler="review",
                    success_label="reviewed",
                ),
            },
            schedule_triggers=[
                ScheduleTriggerConfig(
                    cron="0 9 * * 1",
                    handler="weekly_report",
                    task_prompt="Generate weekly status report",
                ),
            ],
        )

        assert config.mode.label_prefix == "auto/"
        assert len(config.label_triggers) == 1
        assert len(config.schedule_triggers) == 1


class TestProviderEventMap:
    """Test PROVIDER_EVENT_MAP structure and completeness."""

    def test_all_providers_present(self):
        """Test all expected providers are in the map."""
        assert "gitea" in PROVIDER_EVENT_MAP
        assert "github" in PROVIDER_EVENT_MAP
        assert "gitlab" in PROVIDER_EVENT_MAP

    def test_gitea_event_mappings(self):
        """Test Gitea event mappings are correct."""
        gitea = PROVIDER_EVENT_MAP["gitea"]

        assert gitea[TriggerType.LABEL_ADDED] == "issues.labeled"
        assert gitea[TriggerType.PR_OPENED] == "pull_request.opened"
        assert gitea[TriggerType.PUSH] == "push"
        assert gitea[TriggerType.SCHEDULE] == "schedule"

    def test_github_event_mappings(self):
        """Test GitHub event mappings are correct."""
        github = PROVIDER_EVENT_MAP["github"]

        assert github[TriggerType.LABEL_ADDED] == "issues.labeled"
        assert github[TriggerType.PR_OPENED] == "pull_request.opened"
        assert github[TriggerType.MANUAL] == "workflow_dispatch"

    def test_gitlab_event_mappings(self):
        """Test GitLab event mappings are correct."""
        gitlab = PROVIDER_EVENT_MAP["gitlab"]

        assert gitlab[TriggerType.LABEL_ADDED] == "Issue Hook"
        assert gitlab[TriggerType.PR_OPENED] == "Merge Request Hook"
        assert gitlab[TriggerType.PUSH] == "Push Hook"

    def test_gitea_and_github_share_most_events(self):
        """Test Gitea and GitHub share most event names."""
        gitea = PROVIDER_EVENT_MAP["gitea"]
        github = PROVIDER_EVENT_MAP["github"]

        # These should be identical
        shared_triggers = [
            TriggerType.LABEL_ADDED,
            TriggerType.LABEL_REMOVED,
            TriggerType.ISSUE_OPENED,
            TriggerType.PR_OPENED,
            TriggerType.PUSH,
            TriggerType.SCHEDULE,
        ]

        for trigger in shared_triggers:
            assert gitea[trigger] == github[trigger], f"Mismatch for {trigger}"


class TestBackwardCompatibility:
    """Test backward compatibility with existing configurations."""

    @pytest.fixture
    def temp_yaml_file(self, tmp_path: Path) -> Path:
        """Create a temporary YAML file."""
        return tmp_path / "config.yaml"

    def test_settings_without_automation_field(self):
        """Test AutomationSettings works without automation field."""
        from repo_sapiens.config.settings import AutomationSettings

        settings = AutomationSettings(
            git_provider={
                "base_url": "https://gitea.example.com",
                "api_token": "token",
            },
            repository={
                "owner": "org",
                "name": "repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
        )

        # Should have default automation config
        assert isinstance(settings.automation, AutomationConfig)
        assert settings.automation.mode.mode == "hybrid"
        assert settings.automation.label_triggers == {}

    def test_settings_with_partial_automation_field(self):
        """Test AutomationSettings with partial automation config."""
        from repo_sapiens.config.settings import AutomationSettings

        settings = AutomationSettings(
            git_provider={
                "base_url": "https://gitea.example.com",
                "api_token": "token",
            },
            repository={
                "owner": "org",
                "name": "repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
            automation={
                "mode": {
                    "mode": "native",
                },
            },
        )

        assert settings.automation.mode.mode == "native"
        # Other defaults should still apply
        assert settings.automation.mode.native_enabled is True
        assert settings.automation.label_triggers == {}

    def test_yaml_without_automation_section(self, temp_yaml_file: Path):
        """Test loading YAML without automation section."""
        from repo_sapiens.config.settings import AutomationSettings

        config_content = {
            "git_provider": {
                "base_url": "https://gitea.example.com",
                "api_token": "token",
            },
            "repository": {
                "owner": "org",
                "name": "repo",
            },
            "agent_provider": {
                "provider_type": "claude-local",
            },
        }

        with open(temp_yaml_file, "w") as f:
            yaml.dump(config_content, f)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))

        # Should load successfully with default automation
        assert settings.repository.owner == "org"
        assert isinstance(settings.automation, AutomationConfig)

    def test_yaml_with_full_automation_section(self, temp_yaml_file: Path):
        """Test loading YAML with full automation section."""
        from repo_sapiens.config.settings import AutomationSettings

        config_content = {
            "git_provider": {
                "base_url": "https://gitea.example.com",
                "api_token": "token",
            },
            "repository": {
                "owner": "org",
                "name": "repo",
            },
            "agent_provider": {
                "provider_type": "claude-local",
            },
            "automation": {
                "mode": {
                    "mode": "hybrid",
                    "label_prefix": "custom/",
                },
                "label_triggers": {
                    "custom/triage": {
                        "label_pattern": "custom/triage",
                        "handler": "triage",
                    },
                },
                "schedule_triggers": [
                    {
                        "cron": "0 8 * * *",
                        "handler": "daily",
                    },
                ],
            },
        }

        with open(temp_yaml_file, "w") as f:
            yaml.dump(config_content, f)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))

        assert settings.automation.mode.label_prefix == "custom/"
        assert len(settings.automation.label_triggers) == 1
        assert settings.automation.label_triggers["custom/triage"].handler == "triage"
        assert len(settings.automation.schedule_triggers) == 1


class TestModelSerialization:
    """Test model serialization for YAML round-tripping."""

    def test_label_trigger_config_to_dict(self):
        """Test LabelTriggerConfig can be serialized to dict."""
        config = LabelTriggerConfig(
            label_pattern="test",
            handler="handler",
            success_label="done",
        )

        dumped = config.model_dump()

        assert dumped["label_pattern"] == "test"
        assert dumped["handler"] == "handler"
        assert dumped["success_label"] == "done"
        assert dumped["ai_enabled"] is True

    def test_automation_config_to_dict(self):
        """Test AutomationConfig can be serialized to dict."""
        config = AutomationConfig(
            mode=AutomationModeConfig(mode="native"),
            label_triggers={
                "test": LabelTriggerConfig(
                    label_pattern="test",
                    handler="handler",
                ),
            },
        )

        dumped = config.model_dump()

        assert dumped["mode"]["mode"] == "native"
        assert "test" in dumped["label_triggers"]

    def test_automation_config_round_trip(self):
        """Test AutomationConfig survives YAML round-trip."""
        original = AutomationConfig(
            mode=AutomationModeConfig(
                mode="hybrid",
                label_prefix="sapiens/",
            ),
            label_triggers={
                "sapiens/triage": LabelTriggerConfig(
                    label_pattern="sapiens/triage",
                    handler="triage",
                    ai_enabled=True,
                ),
            },
            schedule_triggers=[
                ScheduleTriggerConfig(
                    cron="0 8 * * 1-5",
                    handler="daily",
                ),
            ],
        )

        # Serialize to dict (simulating YAML dump)
        dumped = original.model_dump()

        # Deserialize back (simulating YAML load)
        restored = AutomationConfig(**dumped)

        assert restored.mode.mode == original.mode.mode
        assert restored.mode.label_prefix == original.mode.label_prefix
        assert len(restored.label_triggers) == len(original.label_triggers)
        assert len(restored.schedule_triggers) == len(original.schedule_triggers)
