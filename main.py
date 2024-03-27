from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, EmailField
from wtforms.validators import DataRequired
from flask_bootstrap import Bootstrap5
import stripe

stripe.api_key = "sk_test_51OpUDpJlg66SH4V5Oy3Qk6YXw1Z4mokDs57lILq95KgLguL6JM9Pq5KT7uver004d9t7bxbwzIbAj5hLUuCMU66i00GkAmZFj2"

app = Flask(__name__, static_url_path="")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///flask.db"
app.config["SECRET_KEY"] = "3x4mpl353cr3tk3y"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
Bootstrap5(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000), nullable=False)
    img = db.Column(db.String(1000))
    desc = db.Column(db.String(1000))
    price = db.Column(db.Integer, nullable=False)
    price_id = db.Column(db.String(100))


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    user = db.relationship('User', backref=db.backref('carts', lazy="dynamic"))
    product = db.relationship('Product', backref=db.backref('carts', lazy="dynamic"))


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign up")


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


YOUR_DOMAIN = 'http://localhost:5000'


@app.route("/")
def home():
    result = db.session.execute(db.Select(Product).order_by(Product.id))
    products = result.scalars().all()
    return render_template("index.html", current_user=current_user, products=products)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if form.validate_on_submit():
            hns_password = generate_password_hash(
                form.password.data,
                method="pbkdf2:sha256",
                salt_length=8
            )
            new_user = User(
                name=form.name.data,
                email=form.email.data,
                password=hns_password
            )
            result = db.session.execute(db.select(User).where(User.email == form.email.data))
            user = result.scalar()
            if user:
                return "Error. Email already registered."
            else:
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect("/")
    return render_template("register.html", current_user=current_user, form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            result = db.session.execute(db.select(User).where(User.email == email))
            user = result.scalar()
            if not user:
                flash("That email does not exist.")
                return redirect("/login")
            elif not check_password_hash(user.password, password):
                flash("Incorrect password.")
                return redirect("/login")
            else:
                login_user(user)
                return redirect("/")
    return render_template("login.html", current_user=current_user, form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def get_product(product_id):
    result = db.session.execute(db.select(Product).where(Product.id == product_id))
    product = result.scalar()
    return render_template("product.html", current_user=current_user, product=product)


@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    if request.method == "POST":
        if current_user.is_authenticated:
            product_id = request.form["product_id"]
            quantity = int(request.form["quantity"])

            cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = Cart(user_id=current_user.id, product_id=product_id, quantity=quantity)
                db.session.add(cart_item)
            db.session.commit()
        else:
            flash("You need to login to use our features.")
            return redirect("/login")
        return redirect("/view-cart")


@app.route("/view-cart", methods=["GET", "POST"])
def view_cart():
    if current_user.is_authenticated:
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        cart_details = []
        for cart_item in cart_items:
            product = Product.query.get(cart_item.product_id)
            if product:
                cart_details.append({"product": product, "quantity": cart_item.quantity})
    else:
        flash("You need to login to use our features.")
        return redirect("/login")
    return render_template("cart.html", current_user=current_user, cart=cart_details)


@app.route("/clear-cart", methods=["POST"])
def clear_cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    for cart_item in cart_items:
        db.session.delete(cart_item)
        db.session.commit()
    return redirect("/view-cart")


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()

    line_items = []
    for cart_item in cart_items:
        product = Product.query.get(cart_item.product_id)
        if product:
            line_items.append({
                "price": product.price_id,
                "quantity": cart_item.quantity,
            })

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=line_items,
            mode='payment',
            success_url=YOUR_DOMAIN + '/success.html',
            cancel_url=YOUR_DOMAIN + '/cancel.html',
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
