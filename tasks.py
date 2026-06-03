"""Background task execution."""

import os
from analysis.differential import run_differential_analysis
from analysis.clustering import run_clustering_analysis
from analysis.survival import run_survival_analysis, run_gene_survival_analysis

TASK_REGISTRY = {
    'differential': run_differential_analysis,
    'clustering': run_clustering_analysis,
    'survival': run_survival_analysis,
    'gene_survival': run_gene_survival_analysis
}


def execute_task(task_id: int, app) -> None:
    """Execute analysis task and update database."""
    
    with app.app_context():
        from models import db, AnalysisTask
        
        task = AnalysisTask.query.get(task_id)
        if not task:
            return
        
        task.status = 'running'
        db.session.commit()
        
        try:
            analysis_func = TASK_REGISTRY.get(task.analysis_type)
            if not analysis_func:
                raise ValueError(f"Unknown analysis type: {task.analysis_type}")
            
            output_dir = os.path.join(
                app.config['RESULT_FOLDER'], 
                f'task_{task_id}'
            )
            
            # Pass extra params for gene_survival
            if task.analysis_type == 'gene_survival':
                # Extract gene name from task name or use default
                gene_name = task.task_name.replace('GeneSurvival_', '') or 'TP53'
                result = analysis_func(task.input_file, output_dir, gene_col=gene_name)
            else:
                result = analysis_func(task.input_file, output_dir)
            
            task.status = 'completed'
            task.result_path = output_dir
            task.completed_at = __import__('datetime').datetime.utcnow()
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            import traceback
            task.error_message += f"\n{traceback.format_exc()}"
        
        db.session.commit()