from flask import Blueprint, render_template
from app.services.process_service import get_all_processes, get_process_or_404

process_bp = Blueprint("process", __name__, url_prefix="/process")


@process_bp.route("/<int:process_id>")
def process_graph(process_id):
    process = get_process_or_404(process_id)
    return render_template("process_graph.html", process=process)


@process_bp.route("/map")
def process_map():
    return render_template("process_map.html")


@process_bp.route("/")
def process_list():
    processes = get_all_processes()
    return render_template("process_list.html", processes=processes)


@process_bp.route("/bpmn")
def bpmn_processes():
    processes = get_all_processes()
    return render_template("bpmn_processes.html", processes=processes)