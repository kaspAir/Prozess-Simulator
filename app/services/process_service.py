from app.models import Process


def get_all_processes():
    return Process.query.order_by(Process.id).all()


def get_process_or_404(process_id):
    return Process.query.get_or_404(process_id)