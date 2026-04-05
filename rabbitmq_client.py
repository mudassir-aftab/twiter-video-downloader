"""RabbitMQ client for publishing and consuming download tasks"""
import aio_pika
from aio_pika import ExchangeType
import json
import asyncio
import logging
from typing import Callable, Optional
from config import settings, get_rabbitmq_url
from models import DownloadTask

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """RabbitMQ client for task distribution"""
    
    def __init__(self):
        """Initialize RabbitMQ client"""
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self.queue: Optional[aio_pika.Queue] = None
    
    async def connect(self):
        """Establish RabbitMQ connection"""
        try:
            rabbitmq_url = get_rabbitmq_url()
            self.connection = await aio_pika.connect_robust(rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                name=settings.download_exchange_name,
                type=ExchangeType.DIRECT,
                durable=True
            )
            
            # Declare queue
            self.queue = await self.channel.declare_queue(
                name=settings.download_queue_name,
                durable=True
            )
            
            # Bind queue to exchange
            await self.queue.bind(
                exchange=self.exchange,
                routing_key=settings.download_queue_name
            )
            
            logger.info(f"✅ Connected to RabbitMQ at {settings.rabbitmq_host}:{settings.rabbitmq_port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    async def publish_task(self, task: DownloadTask):
        """Publish download task to RabbitMQ queue"""
        try:
            if not self.channel:
                await self.connect()
            
            message = aio_pika.Message(
                body=task.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await self.exchange.publish(
                message,
                routing_key=settings.download_queue_name
            )
            
            logger.info(f"✅ Task {task.task_id} published to RabbitMQ")
        except Exception as e:
            logger.error(f"❌ Error publishing task: {e}")
            raise
    
    async def consume_tasks(self, callback: Callable):
        """Consume download tasks from RabbitMQ queue"""
        try:
            if not self.queue:
                await self.connect()
            
            logger.info("🔄 Worker started consuming tasks from RabbitMQ...")
            
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            task_data = json.loads(message.body.decode())
                            task = DownloadTask(**task_data)
                            logger.info(f"📩 Received task {task.task_id}")
                            
                            # Call the callback function to process the task
                            await callback(task)
                            
                            
                            # Acknowledge message after successful processing
                            # await message.ack()
                            logger.info(f"✅ Task {task.task_id} acknowledged")
                        except Exception as e:
                            logger.error(f"❌ Error processing task: {e}")
                            # Reject and requeue on error
                            await message.nack(requeue=True)
        except Exception as e:
            logger.error(f"❌ Error consuming tasks: {e}")
            if self.connection:
                await self.close()
            raise
    
    async def close(self):
        """Close RabbitMQ connection"""
        try:
            if self.connection:
                await self.connection.close()
                logger.info("✅ RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
    
    async def health_check(self) -> bool:
        """Check RabbitMQ connection health"""
        try:
            if not self.connection or self.connection.is_closed():
                await self.connect()
            return True
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {e}")
            return False


class RabbitMQPublisher:
    """Simplified publisher for API server"""
    
    def __init__(self):
        self.client = RabbitMQClient()
    
    async def initialize(self):
        """Initialize connection"""
        await self.client.connect()
    
    async def publish_download_task(self, task: DownloadTask):
        """Publish a download task"""
        await self.client.publish_task(task)
    
    async def close(self):
        """Close connection"""
        await self.client.close()


# Global instances
rabbitmq_client = RabbitMQClient()
rabbitmq_publisher = RabbitMQPublisher()
