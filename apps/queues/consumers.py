import json

from channels.generic.websocket import AsyncWebsocketConsumer


class BranchQueueConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for public display boards and staff live queue monitoring."""

    async def connect(self):
        self.branch_id = self.scope["url_route"]["kwargs"]["branch_id"]
        self.group_name = f"branch_{self.branch_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_message(self, event):
        """Receive queue update event and push json to WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "event": event.get("event"),
                    "data": event.get("data", {}),
                }
            )
        )


class TicketLiveConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for a customer watching their individual digital ticket in real time."""

    async def connect(self):
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.group_name = f"ticket_{self.ticket_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_message(self, event):
        """Push status change directly to the customer's phone/screen."""
        await self.send(
            text_data=json.dumps(
                {
                    "event": event.get("event"),
                    "data": event.get("data", {}),
                }
            )
        )
