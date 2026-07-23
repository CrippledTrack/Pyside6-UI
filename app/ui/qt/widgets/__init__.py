"""Qt widgets package.

Prefer leaf imports so plugins do not pull the whole widget set:

    from GUI.app.ui.qt.widgets.card_container import CardContainer
    from GUI.app.ui.qt.widgets.progress_indicator import ProgressIndicator

Shell widgets (used by the main window / controllers):
    AdminRequiredPlaceholder, CardContainer, ErrorPlaceholder,
    LoadingPlaceholder / LoadingDots, NotificationCenterWidget,
    ToastNotification

Plugin toolkit (optional helpers for plugin authors; not required by the shell):
    ProgressIndicator, StreamOutputPanel, LoadingOverlay,
    CardSection, HorizontalCard, InfoCard
"""

__all__: list[str] = []
