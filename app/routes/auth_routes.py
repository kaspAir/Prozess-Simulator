from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.models import User, Invitation
from app.auth.service import verify_password, accept_invitation, set_active_account

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and verify_password(user, password):
            login_user(user)
            session.pop("active_account_id", None)
            session.pop("active_organization_id", None)
            nxt = request.args.get("next") or request.form.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("main.dashboard"))
        flash("E-Mail oder Passwort falsch.", "error")

    return render_template("auth/login.html", next=request.args.get("next", ""))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    inv = Invitation.query.filter_by(token=token, status="pending").first()
    if inv is None:
        return render_template("auth/accept_invite.html", invalid=True, token=token)

    if request.method == "POST":
        name = request.form.get("name") or ""
        password = request.form.get("password") or ""
        if len(password) < 8:
            flash("Passwort muss mindestens 8 Zeichen haben.", "error")
            return render_template("auth/accept_invite.html", inv=inv, token=token)

        user, err = accept_invitation(token, name, password)
        if err:
            flash(err, "error")
            return render_template("auth/accept_invite.html", invalid=True, token=token)

        login_user(user)
        set_active_account(inv.account_id)
        flash("Willkommen! Dein Zugang wurde erstellt.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/accept_invite.html", inv=inv, token=token)
