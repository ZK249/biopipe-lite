"""BioPipe Lite - Lightweight Bioinformatics Analysis Platform."""

import os
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename

from config import Config
from models import db, AnalysisTask
from tasks import execute_task

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Home page with upload form."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and create analysis task."""
    
    # Validate inputs
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    analysis_type = request.form.get('analysis_type', 'differential')
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('Invalid file type. Use CSV or TSV.', 'error')
        return redirect(url_for('index'))
    
    # Save file
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(upload_path)
    
    # Create task record
    task = AnalysisTask(
        task_name=request.form.get('task_name', f'Analysis_{filename}'),
        analysis_type=analysis_type,
        input_file=upload_path
    )
    db.session.add(task)
    db.session.commit()
    
    # Execute task (in production, queue this)
    thread = threading.Thread(target=execute_task, args=(task.id, app))
    thread.start()
    
    flash(f'Task #{task.id} created and running', 'success')
    return redirect(url_for('list_tasks'))

@app.route('/tasks')
def list_tasks():
    """Show all analysis tasks."""
    tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).all()
    return render_template('tasks.html', tasks=tasks)

@app.route('/result/<int:task_id>')
def show_result(task_id: int):
    """Display analysis results with structured data for template."""
    task = AnalysisTask.query.get_or_404(task_id)
    
    if task.status != 'completed':
        flash('Task not completed yet', 'warning')
        return redirect(url_for('list_tasks'))
    
    # Initialize template variables
    summary = {
        'total_genes': 'N/A',
        'total_samples': 'N/A',
        'n_significant': 'N/A',
        'pvalue_threshold': '0.05'
    }
    plots = {}
    table_data = []
    table_columns = []
    numeric_columns = []
    download_files = []
    
    if task.result_path and os.path.exists(task.result_path):
        # List all files in result directory
        all_files = os.listdir(task.result_path)
        
        # Categorize files
        for f in sorted(all_files):
            fpath = os.path.join(task.result_path, f)
            if f.endswith('.csv'):
                download_files.append(f)
            elif f.endswith('.png'):
                # Create URL for static file
                rel_path = os.path.relpath(fpath, os.path.join(app.root_path, 'static'))
                plot_name = f.replace('_', ' ').replace('.png', '').title()
                plots[plot_name] = url_for('static', filename=rel_path)
        
        # Load summary/statistics from CSV files
        for csv_file in ['differential_results.csv', 'cluster_assignments.csv', 'survival_summary.csv']:
            csv_path = os.path.join(task.result_path, csv_file)
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    
                    if csv_file == 'differential_results.csv':
                        summary['total_genes'] = len(df)
                        summary['total_samples'] = 'N/A'
                        if 'significant' in df.columns:
                            summary['n_significant'] = int(df['significant'].sum())
                        if 'padj' in df.columns:
                            summary['pvalue_threshold'] = '0.05 (adjusted)'
                        
                        # Prepare table display
                        display_df = df.head(50)
                        table_columns = display_df.columns.tolist()
                        table_data = display_df.to_dict('records')
                        numeric_columns = display_df.select_dtypes(include=[np.number]).columns.tolist()
                        
                    elif csv_file == 'cluster_assignments.csv':
                        summary['total_samples'] = len(df)
                        if 'cluster' in df.columns:
                            summary['n_significant'] = f"{df['cluster'].nunique()} clusters"
                            
                    elif csv_file == 'survival_summary.csv':
                        # Parse summary file
                        for _, row in df.iterrows():
                            if row['metric'] == 'n_total':
                                summary['total_samples'] = row['value']
                            elif row['metric'] == 'n_events':
                                summary['n_significant'] = f"{row['value']} events"
                                
                except Exception as e:
                    app.logger.error(f"Error reading {csv_file}: {e}")
    
    return render_template(
        'result.html',
        task=task,
        summary=summary,
        plots=plots,
        table_data=table_data,
        table_columns=table_columns,
        numeric_columns=numeric_columns,
        download_files=download_files
    )

@app.route('/download/<int:task_id>/<path:filename>')
def download_file(task_id: int, filename: str):
    """Download result files."""
    task = AnalysisTask.query.get_or_404(task_id)
    if not task.result_path:
        return 'No results', 404
    
    return send_from_directory(task.result_path, filename, as_attachment=True)

if __name__ == '__main__':
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.RESULT_FOLDER, exist_ok=True)
    app.run(debug=True, port=5000)