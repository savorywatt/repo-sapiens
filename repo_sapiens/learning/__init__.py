"""Learning and feedback loop system for continuous improvement.

This package provides mechanisms for learning from past workflow executions,
including feedback collection, pattern recognition, and prompt optimization.

Key Components:
    - FeedbackLoop: Main learning system that captures and applies insights
    - ExecutionHistory: Records of past workflow executions
    - PatternAnalysis: Recognition of successful patterns

Features:
    - Tracks execution success rates across different issue types
    - Learns which prompts and strategies work best
    - Adapts task selection based on past results
    - Records timing and performance metrics

Example:
    >>> from repo_sapiens.learning import FeedbackLoop
    >>> feedback = FeedbackLoop()
    >>> feedback.record_execution(issue, results, duration)
    >>> insights = feedback.get_insights()
"""
