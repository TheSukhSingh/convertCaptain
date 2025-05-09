import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, send_file, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pillow_heif
from PIL import Image
import img2pdf
import io
import zipfile
from datetime import date, datetime, timedelta
import stripe
from werkzeug.utils import secure_filename
from sqlalchemy import func

# --- Load environment variables ---
load_dotenv()

# --- Flask setup ---
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# --- Database setup ---
BASE_DIR = os.getcwd()
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Login manager ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# ↓ return a 401 JSON for XHR/fetch instead of a 302 redirect
@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.is_json or request.headers.get('X-Requested-With')=='XMLHttpRequest':
        return jsonify({'error':'login required'}), 401
    return redirect(url_for('login'))

# --- Stripe setup ---
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
YOUR_DOMAIN = os.getenv('YOUR_DOMAIN')
PLUS_PRICE_ID = os.getenv('PLUS_PRICE_ID')
PRO_PRICE_ID = os.getenv('PRO_PRICE_ID')
stripe.api_key = STRIPE_SECRET_KEY

# --- Models ---
class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)   # free, plus, pro
    conversion_limit = db.Column(db.Integer, nullable=False)
    file_size_limit = db.Column(db.Integer, nullable=True)         # None = unlimited
    batch_allowed = db.Column(db.Boolean, default=False)
    users = db.relationship('User', backref='plan', lazy=True)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    profile_img = db.Column(db.String(300))
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    conversion_count = db.Column(db.Integer, default=0, nullable=False)
    last_reset = db.Column(db.Date, default=date.today, nullable=False)
    stripe_customer_id = db.Column(db.String(100))
    subscription_end = db.Column(db.DateTime)
    conversion_logs = db.relationship('ConversionLog', backref='user', lazy=True)
    payment_history = db.relationship('PaymentHistory', backref='user', lazy=True)

class ConversionLog(db.Model):
    __tablename__ = 'conversion_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    original_filename = db.Column(db.String(200))
    output_format = db.Column(db.String(10))

class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    plan = db.Column(db.String(50))  # 'plus', 'pro'
    amount = db.Column(db.Float)
    status = db.Column(db.String(50))
    stripe_session_id = db.Column(db.String(100), unique=True, nullable=False)


# --- User loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HEIC support ---
pillow_heif.register_heif_opener()
OUTPUT_DIR = os.path.join(BASE_DIR, 'converted')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_heic_to_image(file_storage):
    heif_file = pillow_heif.read_heif(file_storage)
    return Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, 'raw')

def convert_image_to_pdf(image):
    img_bytes = io.BytesIO()
    image.save(img_bytes, format='PNG')
    return img2pdf.convert(img_bytes.getvalue())

@app.before_request
def reset_and_check_subscription():
    if current_user.is_authenticated:
        db.session.refresh(current_user)
        today = date.today()
        if current_user.last_reset < today:
            current_user.conversion_count = 0
            current_user.last_reset = today
        # Expire past subscriptions
        if current_user.subscription_end and current_user.subscription_end < datetime.utcnow():
            free_plan = Plan.query.filter_by(name='free').first()
            current_user.plan = free_plan     # Plan object, not string
            current_user.subscription_end = None
        db.session.commit()


# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        pwd = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        free_plan = Plan.query.filter_by(name='free').first()
        if not free_plan:
            flash('Configuration error')
            return redirect(url_for('register'))
        user = User(email=email, name=name,
                    password_hash=generate_password_hash(pwd),
                    plan_id=free_plan.id)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pwd = request.form['password']
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, pwd):
            flash('Invalid credentials')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/tiers')
def tiers():
    return render_template('tier-comparison.html')

@app.route('/profile')
@login_required
def profile():
    # 7-day chart data
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=6)
    raw = db.session.query(
        func.date(ConversionLog.timestamp), func.count()
    ).filter(
        ConversionLog.user_id==current_user.id,
        ConversionLog.timestamp>=week_ago
    ).group_by(func.date(ConversionLog.timestamp)).all()
    # streak
    streak = 0
    for i in range(30):
        d = date.today() - timedelta(days=i)
        if ConversionLog.query.filter_by(user_id=current_user.id).filter(func.date(ConversionLog.timestamp)==d).count():
            streak += 1
        else:
            break
    # chart data
    date_map = {str(d):c for d,c in raw}
    days = [(today - timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    chart_data = [date_map.get(d,0) for d in days]
    # payments
    payments = PaymentHistory.query.filter_by(user_id=current_user.id).order_by(PaymentHistory.date.desc()).all()
    today = datetime.utcnow().date()
    # beginning of current month
    month_start = today.replace(day=1)

    conversions_today = (
        ConversionLog.query
        .filter(
            ConversionLog.user_id == current_user.id,
            func.date(ConversionLog.timestamp) == today
        )
        .count()
    )
    conversions_month = (
        ConversionLog.query
        .filter(
            ConversionLog.user_id == current_user.id,
            ConversionLog.timestamp >= month_start
        )
        .count()
    )
    return render_template(
        'profile.html',
        chart_data=chart_data,
        streak=streak,
        payment_history=payments,
        conversions_today=conversions_today,
        conversions_month=conversions_month
    )

@app.route('/create-checkout-session/<plan>')
@login_required
def create_checkout_session(plan):
    if plan not in ['plus','pro']:
        flash('Invalid plan')
        return redirect(url_for('tiers'))
    if not current_user.stripe_customer_id:
        cust = stripe.Customer.create(email=current_user.email)
        current_user.stripe_customer_id = cust.id
        db.session.commit()
    price_id = PLUS_PRICE_ID if plan=='plus' else PRO_PRICE_ID
    sess = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=['card'],
        line_items=[{'price':price_id,'quantity':1}],
        mode='subscription',
        success_url=f"{YOUR_DOMAIN}{url_for('profile')}",
        cancel_url=f"{YOUR_DOMAIN}{url_for('tiers')}"
    )
    return redirect(sess.url, code=303)


def update_user_subscription(user, sub, session_id):
    # 1️⃣ Figure out which plan they bought
    price_id = sub['items']['data'][0]['price']['id']
    plan_name = 'plus' if price_id == PLUS_PRICE_ID else 'pro'
    plan_obj  = Plan.query.filter_by(name=plan_name).first()

    # 2️⃣ Normalize period end to UTC datetime
    ends_at = datetime.utcfromtimestamp(sub['current_period_end'])

    # 3️⃣ Pull the real amount (in case you change it in Stripe later)
    amount = sub['items']['data'][0]['price']['unit_amount'] / 100.0

    # 4️⃣ Idempotent payment log
    if not PaymentHistory.query.filter_by(stripe_session_id=session_id).first():
        payment = PaymentHistory(
            user_id=user.id,
            plan=plan_name,
            amount=amount,
            status='succeeded',
            stripe_session_id=session_id
        )
        db.session.add(payment)

    # 5️⃣ Update the user’s plan & expiry
    user.plan = plan_obj
    user.subscription_end = ends_at

    db.session.commit()




@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload    = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return str(e), 400

    # ① First-time checkout
    if event['type'] == 'checkout.session.completed':
        sess = event['data']['object']
        user = User.query.filter_by(stripe_customer_id=sess['customer']).first()
        sub  = stripe.Subscription.retrieve(sess['subscription'])
        if user:
            update_user_subscription(user, sub, sess['id'])

    # ② Monthly renewal
    elif event['type'] == 'invoice.payment_succeeded':
        inv  = event['data']['object']
        sub  = stripe.Subscription.retrieve(inv['subscription'])
        user = User.query.filter_by(stripe_customer_id=sub['customer']).first()
        if user:
            update_user_subscription(user, sub, inv['id'])

    return '', 200







@app.route('/convert', methods=['POST'])
@login_required
def convert():
    if not current_user.is_authenticated:
        return jsonify({'error':'login required'}), 401
    files = request.files.getlist('files')
    fmt = request.form.get('format', 'jpeg').lower()
    plan = current_user.plan  # now uses the Plan model

    # Only Pro can batch-upload
    if len(files) > 1 and not plan.batch_allowed:
        flash('Batch upload is only available for Pro plan.')
        return redirect(url_for('tiers'))

    # Daily limit check
    if current_user.conversion_count >= plan.conversion_limit:
        return "Daily limit reached", 403

    outputs = []
    for f in files:
        # size check
        f.seek(0, os.SEEK_END)
        size_mb = f.tell() / (1024 * 1024)
        f.seek(0)
        if plan.file_size_limit and size_mb > plan.file_size_limit:
            flash(f"{f.filename} exceeds file size limit of {plan.file_size_limit} MB.")
            return redirect(request.url)

        # load image
        image = convert_heic_to_image(f) if f.filename.lower().endswith('.heic') else Image.open(f)

        # convert
        if fmt == 'pdf':
            data = convert_image_to_pdf(image)
            mime, ext = 'application/pdf', 'pdf'
        else:
            buf = io.BytesIO()
            image.save(buf, format=fmt.upper())
            data = buf.getvalue()
            mime, ext = f'image/{fmt}', fmt

        filename = f"{secure_filename(os.path.splitext(f.filename)[0])}.{ext}"
        outputs.append((mime, data, filename))

        # log conversion
        log = ConversionLog(
            user_id=current_user.id,
            original_filename=secure_filename(f.filename),
            output_format=fmt
        )
        db.session.add(log)

    # update count & commit everything
    current_user.conversion_count += len(files)
    db.session.commit()

    # single vs. zip response
    if len(outputs) == 1:
        mime, data, filename = outputs[0]
        return send_file(io.BytesIO(data),
                         as_attachment=True,
                         download_name=filename,
                         mimetype=mime)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for mime, data, filename in outputs:
            zf.writestr(filename, data)
    buf.seek(0)
    return send_file(buf,
                     as_attachment=True,
                     download_name='converted_files.zip',
                     mimetype='application/zip')



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        default_plans = [
            ('free',  3,   15, False),
            ('plus', 15,   30, False),
            ('pro', 200, None, True),
        ]
        for name, conv_limit, size_limit, batch in default_plans:
            if not Plan.query.filter_by(name=name).first():
                db.session.add(
                    Plan(
                        name=name,
                        conversion_limit=conv_limit,
                        file_size_limit=size_limit,
                        batch_allowed=batch
                    )
                )
        db.session.commit()
    app.run(debug=True)