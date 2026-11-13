from django.urls import path

from apps.queues.consumers import BranchQueueConsumer, TicketLiveConsumer

websocket_urlpatterns = [
    path("ws/branch/<uuid:branch_id>/", BranchQueueConsumer.as_asgi(), name="ws_branch_queue"),
    path("ws/ticket/<uuid:ticket_id>/", TicketLiveConsumer.as_asgi(), name="ws_ticket_live"),
]
