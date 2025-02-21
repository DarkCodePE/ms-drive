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
    """Modelo para almacenar el resultado general del análisis"""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("drive_files.id"), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones one-to-one
    initial_evaluation = relationship("CriteriaEvaluationModel", back_populates="analysis_result", uselist=False)
    critical_evaluation = relationship("CriticalEvaluationModel", back_populates="analysis_result", uselist=False)
    mentor_report = relationship("AnalysisDetailsModel", back_populates="analysis_result", uselist=False)


class CriteriaEvaluationModel(Base):
    """Modelo para la evaluación inicial completa"""
    __tablename__ = "criteria_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), unique=True)
    final_score = Column(Float)
    general_recommendations_json = Column(JSON)
    recommended_audiences_json = Column(JSON)
    suggested_questions_json = Column(JSON)

    # Relación con AnalysisResultModel
    analysis_result = relationship("AnalysisResultModel", back_populates="initial_evaluation")

    # Relaciones con criterios individuales
    clarity = relationship("EvaluationCriteriaModel", uselist=False,
                           primaryjoin="and_(CriteriaEvaluationModel.id==EvaluationCriteriaModel.criteria_evaluation_id, "
                                       "EvaluationCriteriaModel.criteria_type=='clarity')")
    audience = relationship("EvaluationCriteriaModel", uselist=False,
                            primaryjoin="and_(CriteriaEvaluationModel.id==EvaluationCriteriaModel.criteria_evaluation_id, "
                                        "EvaluationCriteriaModel.criteria_type=='audience')")
    structure = relationship("EvaluationCriteriaModel", uselist=False,
                             primaryjoin="and_(CriteriaEvaluationModel.id==EvaluationCriteriaModel.criteria_evaluation_id, "
                                         "EvaluationCriteriaModel.criteria_type=='structure')")
    depth = relationship("EvaluationCriteriaModel", uselist=False,
                         primaryjoin="and_(CriteriaEvaluationModel.id==EvaluationCriteriaModel.criteria_evaluation_id, "
                                     "EvaluationCriteriaModel.criteria_type=='depth')")
    questions = relationship("EvaluationCriteriaModel", uselist=False,
                             primaryjoin="and_(CriteriaEvaluationModel.id==EvaluationCriteriaModel.criteria_evaluation_id, "
                                         "EvaluationCriteriaModel.criteria_type=='questions')")


class EvaluationCriteriaModel(Base):
    """Modelo para un criterio individual de evaluación"""
    __tablename__ = "evaluation_criteria"

    id = Column(Integer, primary_key=True, index=True)
    criteria_evaluation_id = Column(Integer, ForeignKey("criteria_evaluations.id"))
    criteria_type = Column(String)  # 'clarity', 'audience', etc.
    score_interview = Column(Integer)
    positives_json = Column(JSON)
    improvements_json = Column(JSON)
    recommendations_json = Column(JSON)

    criteria_evaluation = relationship("CriteriaEvaluationModel")

    def to_dict(self):  # <-- AÑADIR este método to_dict()
        return {
            "score_interview": self.score_interview,
            "positives": self.positives_json,
            "improvements": self.improvements_json,
            "recommendations": self.recommendations_json,
        }


class CriticalEvaluationModel(Base):
    """Modelo para la evaluación crítica"""
    __tablename__ = "critical_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), unique=True)
    team_id = Column(String)
    specificity_of_improvements = Column(Boolean)
    identified_improvement_opportunities = Column(Boolean)
    reflective_quality_scores = Column(Boolean)
    notes = Column(Text)

    analysis_result = relationship("AnalysisResultModel", back_populates="critical_evaluation")


class AnalysisDetailsModel(Base):
    """Modelo para detalles del análisis"""
    __tablename__ = "analysis_details"

    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), unique=True)
    validated_insights_json = Column(JSON)
    pending_hypotheses_json = Column(JSON)
    identified_gaps_json = Column(JSON)
    action_items_json = Column(JSON)

    analysis_result = relationship("AnalysisResultModel", back_populates="mentor_report")
    mentor_details = relationship("MentorReportDetailsModel", back_populates="analysis_details", uselist=False)


class MentorReportDetailsModel(Base):
    """Modelo para detalles del reporte del mentor"""
    __tablename__ = "mentor_report_details"

    id = Column(Integer, primary_key=True, index=True)
    analysis_details_id = Column(Integer, ForeignKey("analysis_details.id"), unique=True)
    executive_summary = Column(Text)
    key_findings_json = Column(JSON)
    discussion_points_json = Column(JSON)
    recommended_questions_json = Column(JSON)
    next_steps_json = Column(JSON)
    alerts_json = Column(JSON)

    analysis_details = relationship("AnalysisDetailsModel", back_populates="mentor_details")

    def to_dict(self):
        return {
            "executive_summary": self.executive_summary,
            "key_findings": self.key_findings_json,
            "discussion_points": self.discussion_points_json,
            "recommended_questions": self.recommended_questions_json,
            "next_steps": self.next_steps_json,
            "alerts": self.alerts_json
        }


class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: Optional[str] = None
    webViewLink: Optional[str] = None

    class Config:
        from_attributes = True
