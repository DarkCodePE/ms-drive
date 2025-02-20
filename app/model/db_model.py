from datetime import datetime
from typing import Optional

from openai import BaseModel
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean, JSON, Float, Text
from sqlalchemy.orm import relationship, backref

from app.config.base import Base  # Se asume que Base está definido en tu configuración de la BD


class DriveFolderModel(Base):
    """Modelo para representar las carpetas en la base de datos"""
    __tablename__ = "drive_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    google_drive_folder_id = Column(String, nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("drive_folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Modificamos la relación children para manejar correctamente la recursividad
    children = relationship(
        "DriveFolderModel",
        backref=backref('parent', remote_side=[id]),
        cascade="all, delete-orphan"
    )

    # Relación con documentos
    documents = relationship(
        "DriveFileModel",
        backref="folder",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<DriveFolderModel(id={self.id}, name='{self.name}')>"


class DriveFileModel(Base):
    __tablename__ = "drive_files"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    file_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String, index=True)
    mime_type = Column(String(255), nullable=False)
    modified_time = Column(DateTime, nullable=False)
    web_view_link = Column(String(1000), nullable=True)
    detected_at = Column(DateTime, nullable=True)
    processed = Column(Boolean, default=False)
    folder_id = Column(Integer, ForeignKey("drive_folders.id"))  # Clave foránea a la carpeta contenedora
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DriveDocumentModel(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "web_view_link": self.web_view_link,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


class AnalysisResultModel(Base):
    """Modelo para almacenar el resultado general del análisis, punto de entrada."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("drive_files.id"), unique=True)
    initial_evaluation_id = Column(Integer, ForeignKey("criteria_evaluations.id"))
    critical_evaluation_id = Column(Integer, ForeignKey("critical_evaluations.id"))
    mentor_report_id = Column(Integer, ForeignKey("analysis_details.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    initial_evaluation = relationship("CriteriaEvaluationModel", backref="analysis_result")  # Relación one-to-one
    critical_evaluation = relationship("CriticalEvaluationModel", backref="analysis_result")  # Relación one-to-one
    mentor_report = relationship("AnalysisDetailsModel", backref="analysis_result")  # Relación one-to-one

    def __repr__(self):
        return f"<AnalysisResultModel(id={self.id}, file_id={self.file_id})>"


class CriteriaEvaluationModel(Base):
    """Modelo para la evaluación inicial completa (CriteriaEvaluationDict)"""
    __tablename__ = "criteria_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    final_score = Column(Float)
    general_recommendations_json = Column(JSON)  # o Text si prefieres string
    recommended_audiences_json = Column(JSON)  # o Text si prefieres string
    suggested_questions_json = Column(JSON)  # o Text si prefieres string

    clarity = relationship("EvaluationCriteriaModel",
                           foreign_keys="EvaluationCriteriaModel.criteria_evaluation_clarity_id",
                           uselist=False)  # Relación one-to-one
    audience = relationship("EvaluationCriteriaModel",
                            foreign_keys="EvaluationCriteriaModel.criteria_evaluation_audience_id",
                            uselist=False)  # Relación one-to-one
    structure = relationship("EvaluationCriteriaModel",
                             foreign_keys="EvaluationCriteriaModel.criteria_evaluation_structure_id",
                             uselist=False)  # Relación one-to-one
    depth = relationship("EvaluationCriteriaModel", foreign_keys="EvaluationCriteriaModel.criteria_evaluation_depth_id",
                         uselist=False)  # Relación one-to-one
    questions = relationship("EvaluationCriteriaModel",
                             foreign_keys="EvaluationCriteriaModel.criteria_evaluation_questions_id",
                             uselist=False)  # Relación one-to-one
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"))  # Clave foránea a AnalysisResultModel


class EvaluationCriteriaModel(Base):
    """Modelo para un criterio individual de evaluación (EvaluationCriteriaDict)"""
    __tablename__ = "evaluation_criteria"

    id = Column(Integer, primary_key=True, index=True)
    score_interview = Column(Integer)
    positives_json = Column(JSON)  # o Text si prefieres string
    improvements_json = Column(JSON)  # o Text si prefieres string
    recommendations_json = Column(JSON)  # o Text si prefieres string
    criteria_evaluation_clarity_id = Column(Integer, ForeignKey("criteria_evaluations.id"),
                                            nullable=True)  # Clave foránea a CriteriaEvaluationModel (para 'clarity')
    criteria_evaluation_audience_id = Column(Integer, ForeignKey("criteria_evaluations.id"),
                                             nullable=True)  # Clave foránea a CriteriaEvaluationModel (para 'audience')
    criteria_evaluation_structure_id = Column(Integer, ForeignKey("criteria_evaluations.id"),
                                              nullable=True)  # Clave foránea a CriteriaEvaluationModel (para 'structure')
    criteria_evaluation_depth_id = Column(Integer, ForeignKey("criteria_evaluations.id"),
                                          nullable=True)  # Clave foránea a CriteriaEvaluationModel (para 'depth')
    criteria_evaluation_questions_id = Column(Integer, ForeignKey("criteria_evaluations.id"),
                                              nullable=True)  # Clave foránea a CriteriaEvaluationModel (para 'questions')


class CriticalEvaluationModel(Base):
    """Modelo para la evaluación crítica (CriticalEvaluationDict)"""
    __tablename__ = "critical_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(String)  # team_id como String
    specificity_of_improvements = Column(Boolean)
    identified_improvement_opportunities = Column(Boolean)
    reflective_quality_scores = Column(Boolean)
    notes = Column(Text)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"))  # Clave foránea a AnalysisResultModel


class AnalysisDetailsModel(Base):
    """Modelo para AnalysisDetails (MentorReportDetails + AnalysisDetails)"""
    __tablename__ = "analysis_details"

    id = Column(Integer, primary_key=True, index=True)
    validated_insights_json = Column(JSON)  # o Text si prefieres string
    pending_hypotheses_json = Column(JSON)  # o Text si prefieres string
    identified_gaps_json = Column(JSON)  # o Text si prefieres string
    action_items_json = Column(JSON)  # o Text si prefieres string
    mentor_details_id = Column(Integer,
                               ForeignKey("mentor_report_details.id"))  # Clave foránea a MentorReportDetailsModel
    mentor_details = relationship("MentorReportDetailsModel", backref="analysis_details",
                                  uselist=False)  # Relación one-to-one
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"))  # Clave foránea a AnalysisResultModel


class MentorReportDetailsModel(Base):
    """Modelo para MentorReportDetails (parte de AnalysisDetails)"""
    __tablename__ = "mentor_report_details"

    id = Column(Integer, primary_key=True, index=True)
    executive_summary = Column(Text)
    key_findings_json = Column(JSON)  # o Text si prefieres string
    discussion_points_json = Column(JSON)  # o Text si prefieres string
    recommended_questions_json = Column(JSON)  # o Text si prefieres string
    next_steps_json = Column(JSON)  # o Text si prefieres string
    alerts_json = Column(JSON)  # o Text si prefieres string
    analysis_details_id = Column(Integer, ForeignKey("analysis_details.id"))  # Clave foránea a AnalysisDetailsModel


class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: Optional[str] = None
    webViewLink: Optional[str] = None

    class Config:
        from_attributes = True
