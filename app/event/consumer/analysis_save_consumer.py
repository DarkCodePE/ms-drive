import asyncio
import json
import logging
from typing import Dict, Any

import aiokafka
from fastapi import HTTPException
from aiokafka.errors import KafkaError

from sqlalchemy.orm import Session
from app.model.db_model import DriveFileModel, DriveFolderModel, AnalysisDetailsModel, MentorReportDetailsModel, \
    CriticalEvaluationModel, EvaluationCriteriaModel, CriteriaEvaluationModel, AnalysisResultModel

from app.config.database import db_manager

logger = logging.getLogger(__name__)


class AnalysisSaveConsumer:
    def __init__(self):
        self.consumer = aiokafka.AIOKafkaConsumer(
            'analysis-events',  # Tópico de Kafka al que se suscribe para recibir eventos de análisis
            bootstrap_servers='localhost:9092',  # Asegúrate de que coincida con tu configuración de Kafka
            group_id='analysis-saver-group',  # Un group_id para este consumidor
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),  # Deserializador JSON
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            max_poll_records=10
        )

    async def start(self):
        """Inicia el consumidor de eventos de análisis."""
        logger.info("Iniciando consumidor de eventos de análisis...")
        try:
            await self.consumer.start()
            logger.info("Consumidor de eventos de análisis iniciado y esperando mensajes...")

            while True:  # Loop continuo para consumir mensajes
                try:
                    async for message in self.consumer:
                        try:
                            logger.info(f"Mensaje de análisis recibido: {message.value}")
                            await self.process_analysis_event(message.value)
                            await self.consumer.commit()  # Commit offset si el procesamiento fue exitoso
                        except Exception as e:
                            logger.error(f"Error procesando mensaje de análisis individual: {str(e)}")
                            continue  # Continuar al siguiente mensaje en caso de error en el procesamiento

                except Exception as e:
                    logger.error(f"Error en el consumo de mensajes de análisis: {str(e)}")
                    await asyncio.sleep(5)  # Esperar antes de reintentar en caso de error de consumo
                    continue

        except Exception as e:
            logger.error(f"Error fatal en el consumidor de análisis: {str(e)}")
            raise
        finally:
            await self.consumer.stop()

    async def stop(self):
        """Detiene el consumidor de eventos de análisis."""
        logger.info("Deteniendo consumidor de eventos de análisis...")
        await self.consumer.stop()
        logger.info("Consumidor de eventos de análisis detenido.")

    async def process_analysis_event(self, event: Dict[str, Any]):
        """
        Procesa un evento de análisis recibido de Kafka y guarda los resultados en la base de datos.
        """
        file_id_drive = event.get('file_id')  # Obtener file_id de Google Drive del evento
        analysis_results = event.get('analysis_results')  # Obtener resultados del análisis del evento
        print("file_id_drive -> kafka", file_id_drive)
        print("analysis_results -> kafka", analysis_results)
        if not file_id_drive or not analysis_results:
            logger.warning(f"Evento de análisis incompleto recibido: {event}")
            return

        logger.info(f"Procesando evento de análisis para file_id: {file_id_drive}")

        try:
            with db_manager.get_db() as db:  # Obtener sesión de base de datos usando context manager
                db_file = db.query(DriveFileModel).filter(DriveFileModel.file_id == file_id_drive).first()
                if not db_file:
                    logger.warning(
                        f"DriveFileModel no encontrado en la base de datos para file_id: {file_id_drive}. Imposible guardar resultados del análisis.")
                    return

                # --- Lógica para guardar los resultados del análisis en la base de datos (modelo granular) ---
                analysis_result_db = AnalysisResultModel(
                    file_id=db_file.id)  # Crear AnalysisResultModel, pasando file_id como argumento
                analysis_result_db.drive_file = db_file  # Establecer la relación *después* de crear la instancia

                # Guardar CriteriaEvaluationModel y EvaluationCriteriaModels
                initial_evaluation_data = analysis_results.get("initial_evaluation")
                criteria_evaluation_db = CriteriaEvaluationModel(
                    analysis_result=analysis_result_db,  # Establecer relación inversa
                    final_score=initial_evaluation_data.get("final_score"),
                    general_recommendations_json=initial_evaluation_data.get("general_recommendations"),
                    recommended_audiences_json=initial_evaluation_data.get("recommended_audiences"),
                    suggested_questions_json=initial_evaluation_data.get("suggested_questions")
                )
                criteria_evaluation_db.clarity = EvaluationCriteriaModel(criteria_evaluation=criteria_evaluation_db,
                                                                         **initial_evaluation_data.get(
                                                                             "clarity"))  # Crear y relacionar EvaluationCriteriaModel para claridad
                criteria_evaluation_db.audience = EvaluationCriteriaModel(criteria_evaluation=criteria_evaluation_db,
                                                                          **initial_evaluation_data.get(
                                                                              "audience"))  # Crear y relacionar EvaluationCriteriaModel para audiencia
                criteria_evaluation_db.structure = EvaluationCriteriaModel(criteria_evaluation=criteria_evaluation_db,
                                                                           **initial_evaluation_data.get(
                                                                               "structure"))  # Crear y relacionar EvaluationCriteriaModel para estructura
                criteria_evaluation_db.depth = EvaluationCriteriaModel(criteria_evaluation=criteria_evaluation_db,
                                                                       **initial_evaluation_data.get(
                                                                           "depth"))  # Crear y relacionar EvaluationCriteriaModel para profundidad
                criteria_evaluation_db.questions = EvaluationCriteriaModel(criteria_evaluation=criteria_evaluation_db,
                                                                           **initial_evaluation_data.get(
                                                                               "questions"))  # Crear y relacionar EvaluationCriteriaModel para preguntas
                db.add(criteria_evaluation_db)
                analysis_result_db.initial_evaluation = criteria_evaluation_db  # Establecer relación en AnalysisResultModel

                # Guardar CriticalEvaluationModel
                critical_evaluation_data = analysis_results.get("critical_evaluation")
                critical_evaluation_db = CriticalEvaluationModel(analysis_result=analysis_result_db,
                                                                 **critical_evaluation_data)  # Crear CriticalEvaluationModel y establecer relación
                db.add(critical_evaluation_db)
                analysis_result_db.critical_evaluation = critical_evaluation_db  # Establecer relación en AnalysisResultModel

                # Guardar AnalysisDetailsModel y MentorReportDetailsModel
                mentor_report_data = analysis_results.get("mentor_report")
                mentor_details_data = mentor_report_data.get("mentor_details")
                mentor_details_db = MentorReportDetailsModel(
                    executive_summary=mentor_details_data.get("executive_summary"),
                    key_findings_json=mentor_details_data.get("key_findings"),
                    discussion_points_json=mentor_details_data.get("discussion_points"),
                    recommended_questions_json=mentor_details_data.get("recommended_questions"),
                    next_steps_json=mentor_details_data.get("next_steps"),
                    alerts_json=mentor_details_data.get("alerts"),
                )
                db.add(mentor_details_db)
                analysis_details_db = AnalysisDetailsModel(
                    analysis_result=analysis_result_db,  # Establecer relación inversa
                    validated_insights_json=mentor_report_data.get("validated_insights"),
                    pending_hypotheses_json=mentor_report_data.get("pending_hypotheses"),
                    identified_gaps_json=mentor_report_data.get("identified_gaps"),
                    action_items_json=mentor_report_data.get("action_items"),
                    mentor_details=mentor_details_db  # Asignar MentorReportDetailsModel
                )
                db.add(analysis_details_db)
                analysis_result_db.mentor_report = analysis_details_db  # Establecer relación en AnalysisResultModel

                db.add(analysis_result_db)  # Añadir AnalysisResultModel al final, después de relaciones
                db.commit()  # Commit la transacción después de guardar todos los datos
                logger.info(
                    f"Resultados del análisis guardados exitosamente en la base de datos para file_id: {file_id_drive}")

        except Exception as e:
            logger.error(f"Error al procesar y guardar el evento de análisis para file_id {file_id_drive}: {str(e)}")
            raise KafkaError(f"Error al procesar evento de análisis: {str(e)}")
