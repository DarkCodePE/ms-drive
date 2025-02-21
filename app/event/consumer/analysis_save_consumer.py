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

    # async def process_analysis_event(self, event: Dict[str, Any]):
    #     """
    #     Procesa un evento de análisis recibido de Kafka y guarda los resultados en la base de datos.
    #     """
    #     file_id_drive = event.get('file_id')
    #     analysis_results = event.get('analysis_results')
    #
    #     if not file_id_drive or not analysis_results:
    #         logger.warning(f"Evento de análisis incompleto recibido: {event}")
    #         return
    #
    #     logger.info(f"Procesando evento de análisis para file_id: {file_id_drive}")
    #
    #     try:
    #         with db_manager.get_db() as db:
    #             # Buscar el archivo
    #             db_file = db.query(DriveFileModel).filter(DriveFileModel.file_id == file_id_drive).first()
    #             if not db_file:
    #                 logger.warning(f"DriveFileModel no encontrado para file_id: {file_id_drive}")
    #                 return
    #
    #             # 1. Crear el AnalysisResult primero
    #             analysis_result = AnalysisResultModel(
    #                 file_id=db_file.id
    #             )
    #             db.add(analysis_result)
    #             db.flush()  # Para obtener el ID
    #
    #             # 2. Crear y relacionar CriteriaEvaluation
    #             initial_evaluation_data = analysis_results.get("initial_evaluation", {})
    #             criteria_evaluation = CriteriaEvaluationModel(
    #                 analysis_result_id=analysis_result.id,
    #                 final_score=initial_evaluation_data.get("final_score", 0.0),
    #                 general_recommendations_json=initial_evaluation_data.get("general_recommendations", []),
    #                 recommended_audiences_json=initial_evaluation_data.get("recommended_audiences", []),
    #                 suggested_questions_json=initial_evaluation_data.get("suggested_questions", {})
    #             )
    #             db.add(criteria_evaluation)
    #             db.flush()
    #
    #             # 3. Crear criterios individuales
    #             for criteria_type in ["clarity", "audience", "structure", "depth", "questions"]:
    #                 criteria_data = initial_evaluation_data.get(criteria_type, {})
    #                 criteria = EvaluationCriteriaModel(
    #                     score_interview=criteria_data.get("score_interview", 0),
    #                     positives_json=criteria_data.get("positives", []),
    #                     improvements_json=criteria_data.get("improvements", []),
    #                     recommendations_json=criteria_data.get("recommendations", [])
    #                 )
    #
    #                 # Asignar el ID del criterio al campo correspondiente en criteria_evaluation
    #                 if criteria_type == "clarity":
    #                     criteria.criteria_evaluation_clarity_id = criteria_evaluation.id
    #                 elif criteria_type == "audience":
    #                     criteria.criteria_evaluation_audience_id = criteria_evaluation.id
    #                 elif criteria_type == "structure":
    #                     criteria.criteria_evaluation_structure_id = criteria_evaluation.id
    #                 elif criteria_type == "depth":
    #                     criteria.criteria_evaluation_depth_id = criteria_evaluation.id
    #                 elif criteria_type == "questions":
    #                     criteria.criteria_evaluation_questions_id = criteria_evaluation.id
    #
    #                 db.add(criteria)
    #
    #             # 4. Crear CriticalEvaluation
    #             critical_evaluation_data = analysis_results.get("critical_evaluation", {})
    #             critical_evaluation = CriticalEvaluationModel(
    #                 analysis_result_id=analysis_result.id,
    #                 team_id=critical_evaluation_data.get("team_id"),
    #                 specificity_of_improvements=critical_evaluation_data.get("specificity_of_improvements", False),
    #                 identified_improvement_opportunities=critical_evaluation_data.get(
    #                     "identified_improvement_opportunities", False),
    #                 reflective_quality_scores=critical_evaluation_data.get("reflective_quality_scores", False),
    #                 notes=critical_evaluation_data.get("notes", "")
    #             )
    #             db.add(critical_evaluation)
    #             db.flush()
    #
    #             # 5. Crear MentorReportDetails
    #             mentor_report_data = analysis_results.get("mentor_report", {})
    #             mentor_details_data = mentor_report_data.get("mentor_details", {})
    #             mentor_details = MentorReportDetailsModel(
    #                 executive_summary=mentor_details_data.get("executive_summary", ""),
    #                 key_findings_json=mentor_details_data.get("key_findings", []),
    #                 discussion_points_json=mentor_details_data.get("discussion_points", []),
    #                 recommended_questions_json=mentor_details_data.get("recommended_questions", []),
    #                 next_steps_json=mentor_details_data.get("next_steps", []),
    #                 alerts_json=mentor_details_data.get("alerts", [])
    #             )
    #             db.add(mentor_details)
    #             db.flush()
    #
    #             # 6. Crear AnalysisDetails
    #             analysis_details = AnalysisDetailsModel(
    #                 analysis_result_id=analysis_result.id,
    #                 mentor_details_id=mentor_details.id,
    #                 validated_insights_json=mentor_report_data.get("validated_insights", []),
    #                 pending_hypotheses_json=mentor_report_data.get("pending_hypotheses", []),
    #                 identified_gaps_json=mentor_report_data.get("identified_gaps", []),
    #                 action_items_json=mentor_report_data.get("action_items", [])
    #             )
    #             db.add(analysis_details)
    #
    #             # 7. Commit final
    #             db.commit()
    #             logger.info(f"Análisis guardado exitosamente para file_id: {file_id_drive}")
    #
    #     except Exception as e:
    #         logger.error(f"Error procesando análisis para file_id {file_id_drive}: {str(e)}", exc_info=True)
    #         raise KafkaError(f"Error al procesar evento de análisis: {str(e)}")

    async def process_analysis_event(self, event: Dict[str, Any]):
        """
        Procesa un evento de análisis recibido de Kafka y guarda los resultados en la base de datos.
        """
        file_id_drive = event.get('file_id')
        analysis_results = event.get('analysis_results')

        if not file_id_drive or not analysis_results:
            logger.warning(f"Evento de análisis incompleto recibido: {event}")
            return

        logger.info(f"Procesando evento de análisis para file_id: {file_id_drive}")

        try:
            with db_manager.get_db() as db:
                # Buscar el archivo
                db_file = db.query(DriveFileModel).filter(DriveFileModel.file_id == file_id_drive).first()
                if not db_file:
                    logger.warning(f"DriveFileModel no encontrado para file_id: {file_id_drive}")
                    return

                try:
                    # 1. Crear AnalysisResult
                    analysis_result = AnalysisResultModel(file_id=db_file.id)
                    db.add(analysis_result)
                    db.flush()
                    logger.debug(f"AnalysisResult creado con ID: {analysis_result.id}")

                    # 2. Crear CriteriaEvaluation
                    initial_evaluation_data = analysis_results.get("initial_evaluation", {})
                    criteria_evaluation = CriteriaEvaluationModel(
                        analysis_result_id=analysis_result.id,
                        final_score=initial_evaluation_data.get("final_score", 0.0),
                        general_recommendations_json=initial_evaluation_data.get("general_recommendations", []),
                        recommended_audiences_json=initial_evaluation_data.get("recommended_audiences", []),
                        suggested_questions_json=initial_evaluation_data.get("suggested_questions", {})
                    )
                    db.add(criteria_evaluation)
                    db.flush()
                    logger.debug(f"CriteriaEvaluation creado con ID: {criteria_evaluation.id}")

                    # 3. Crear criterios individuales
                    for criteria_type in ["clarity", "audience", "structure", "depth", "questions"]:
                        criteria_data = initial_evaluation_data.get(criteria_type, {})
                        criteria = EvaluationCriteriaModel(
                            criteria_evaluation_id=criteria_evaluation.id,
                            criteria_type=criteria_type,
                            score_interview=criteria_data.get("score_interview", 0),
                            positives_json=criteria_data.get("positives", []),
                            improvements_json=criteria_data.get("improvements", []),
                            recommendations_json=criteria_data.get("recommendations", [])
                        )
                        db.add(criteria)
                    logger.debug("Criterios individuales creados")

                    # 4. Crear CriticalEvaluation
                    critical_evaluation_data = analysis_results.get("critical_evaluation", {})
                    critical_evaluation = CriticalEvaluationModel(
                        analysis_result_id=analysis_result.id,
                        team_id=critical_evaluation_data.get("team_id"),
                        specificity_of_improvements=critical_evaluation_data.get("specificity_of_improvements", False),
                        identified_improvement_opportunities=critical_evaluation_data.get(
                            "identified_improvement_opportunities", False),
                        reflective_quality_scores=critical_evaluation_data.get("reflective_quality_scores", False),
                        notes=critical_evaluation_data.get("notes", "")
                    )
                    db.add(critical_evaluation)
                    db.flush()
                    logger.debug(f"CriticalEvaluation creado con ID: {critical_evaluation.id}")

                    # 5. Crear MentorReportDetails
                    mentor_report_data = analysis_results.get("mentor_report", {})
                    mentor_details_data = mentor_report_data.get("mentor_details", {})

                    # 6. Crear AnalysisDetails primero
                    analysis_details = AnalysisDetailsModel(
                        analysis_result_id=analysis_result.id,
                        validated_insights_json=mentor_report_data.get("validated_insights", []),
                        pending_hypotheses_json=mentor_report_data.get("pending_hypotheses", []),
                        identified_gaps_json=mentor_report_data.get("identified_gaps", []),
                        action_items_json=mentor_report_data.get("action_items", [])
                    )
                    db.add(analysis_details)
                    db.flush()
                    logger.debug(f"AnalysisDetails creado con ID: {analysis_details.id}")

                    # 7. Crear MentorReportDetails después
                    mentor_details = MentorReportDetailsModel(
                        analysis_details_id=analysis_details.id,
                        executive_summary=mentor_details_data.get("executive_summary", ""),
                        key_findings_json=mentor_details_data.get("key_findings", []),
                        discussion_points_json=mentor_details_data.get("discussion_points", []),
                        recommended_questions_json=mentor_details_data.get("recommended_questions", []),
                        next_steps_json=mentor_details_data.get("next_steps", []),
                        alerts_json=mentor_details_data.get("alerts", [])
                    )
                    db.add(mentor_details)

                    # 8. Commit final
                    db.commit()
                    logger.info(f"Análisis guardado exitosamente para file_id: {file_id_drive}")

                except Exception as e:
                    db.rollback()
                    logger.error(f"Error durante la creación de entidades: {str(e)}")
                    raise

        except Exception as e:
            logger.error(f"Error procesando análisis para file_id {file_id_drive}: {str(e)}", exc_info=True)
            raise KafkaError(f"Error al procesar evento de análisis: {str(e)}")