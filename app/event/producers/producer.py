import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'


class KafkaProducer:
    def __init__(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=self._serialize_value,
            request_timeout_ms=10000
        )
        self._started = False

    def _serialize_value(self, value: Dict[str, Any]) -> bytes:
        """
        Serializa y valida el valor antes de enviarlo.
        """
        try:
            # Validar estructura básica del evento
            required_fields = ['type', 'data', 'metadata']
            if not all(field in value for field in required_fields):
                missing_fields = [field for field in required_fields if field not in value]
                raise ValueError(f"Missing required fields in event: {missing_fields}")

            # Validar que los datos no sean None
            if value.get('data') is None:
                raise ValueError("Event data cannot be None")

            # Validar metadatos
            metadata = value.get('metadata', {})
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")

            return json.dumps(value).encode('utf-8')
        except Exception as e:
            logger.error(f"Error serializing event: {str(e)}")
            raise

    async def start(self):
        if not self._started:
            try:
                await self._producer.start()
                self._started = True
                logger.info("Kafka producer started successfully")
            except Exception as e:
                logger.error(f"Error starting Kafka producer: {str(e)}")
                raise

    async def stop(self):
        if self._started:
            try:
                await self._producer.stop()
                logger.info("Kafka producer stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping Kafka producer: {str(e)}")
            finally:
                self._started = False

    async def send_event(self, topic: str, event: Dict[str, Any]) -> Optional[dict]:
        """
        Envía un evento a Kafka con validación y manejo de errores mejorado.

        Returns:
            dict: El evento enviado si fue exitoso, None si hubo un error
        """
        if not self._started:
            try:
                await self.start()
            except Exception as e:
                logger.error(f"Failed to start producer: {str(e)}")
                return None

        try:
            # Registrar el evento que se intenta enviar
            logger.debug(f"Attempting to send event to topic {topic}: {event}")
            #print(f"Attempting to send event to topic {topic}: {event}")
            # Intentar enviar el mensaje
            await self._producer.send_and_wait(topic, event)
            #print(f"Event sent to Kafka: {event['type']}")
            logger.info(f"Successfully sent event type '{event.get('type')}' to topic {topic}")
            logger.debug(f"Event details: {event}")

            return event

        except Exception as e:
            logger.error(f"Failed to send event to topic {topic}: {str(e)}")
            logger.error(f"Event that failed: {event}")
            raise

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
