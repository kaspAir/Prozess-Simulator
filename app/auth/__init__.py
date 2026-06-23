from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Bitte zuerst anmelden."


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db_get(User, user_id)


def db_get(model, pk):
    from app.models import db
    return db.session.get(model, int(pk))
