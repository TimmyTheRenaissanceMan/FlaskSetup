from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import LoginForm, RegisterForm, CreateProjectForm, CommentForm
from flask_gravatar import Gravatar
import os

app = Flask(__name__)
# noinspection PyPackageRequirements
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLE
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    projects = relationship("Project", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="projects")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_project")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    parent_project = relationship("Project", back_populates="comments")
    comment_author = relationship("User", back_populates="comments")
    text = db.Column(db.Text, nullable=False)
db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_projects():
    projects = Project.query.all()
    return render_template("index.html", all_projects=projects, current_user=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        if User.query.filter_by(email=form.email.data).first():
            print(User.query.filter_by(email=form.email.data).first())
            #User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_projects"))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        # Email doesn't exist or password incorrect.
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_projects'))
    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_projects'))


@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def show_project(project_id):
    form = CommentForm()
    requested_project = Project.query.get(project_id)

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.comment_text.data,
            comment_author=current_user,
            parent_project=requested_project
        )
        db.session.add(new_comment)
        db.session.commit()

    return render_template("project.html", project=requested_project, form=form, current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-project", methods=["GET", "POST"])
@admin_only
def add_new_project():
    form = CreateProjectForm()
    if form.validate_on_submit():
        new_project = Project(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_project)
        db.session.commit()
        return redirect(url_for("get_all_projects"))

    return render_template("make-project.html", form=form, current_user=current_user)




@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
@admin_only
def edit_project(project_id):
    project = Project.query.get(project_id)
    edit_form = CreateProjectForm(
        title=project.title,
        subtitle=project.subtitle,
        img_url=project.img_url,
        author=current_user,
        body=project.body
    )
    if edit_form.validate_on_submit():
        project.title = edit_form.title.data
        project.subtitle = edit_form.subtitle.data
        project.img_url = edit_form.img_url.data
        project.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_project", project_id=project.id))

    return render_template("make-project.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:project_id>")
@admin_only
def delete_project(project_id):
    project_to_delete = Project.query.get(project_id)
    db.session.delete(project_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_projects'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
