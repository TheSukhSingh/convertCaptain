import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, send_file, redirect, session, url_for, flash, g, make_response
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
from sqlalchemy import func, text
from flask_migrate    import Migrate
from datetime import datetime
load_dotenv()
from sqlalchemy.exc import OperationalError

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "converted")

INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False




db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.is_json or request.headers.get('X-Requested-With')=='XMLHttpRequest':
        return jsonify({'error':'login required'}), 401
    return redirect(url_for('login'))

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
YOUR_DOMAIN = os.getenv('YOUR_DOMAIN')
PLUS_PRICE_ID = os.getenv('PLUS_PRICE_ID')
PRO_PRICE_ID = os.getenv('PRO_PRICE_ID')
stripe.api_key = STRIPE_SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)   
    conversion_limit = db.Column(db.Integer, nullable=False)
    file_size_limit = db.Column(db.Integer, nullable=True)       
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
    __table_args__     = (
        db.Index('ix_conversionlog_user_timestamp', 'user_id', 'timestamp'),
    )
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    timestamp          = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    original_filename  = db.Column(db.String(128))
    output_format      = db.Column(db.String(10))

class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    plan = db.Column(db.String(50)) 
    amount = db.Column(db.Float)
    status = db.Column(db.String(50))
    stripe_session_id = db.Column(db.String(100), unique=True, nullable=False)

class Guest(db.Model):
    __tablename__ = 'guest'
    anon_id         = db.Column(db.String(36), primary_key=True)
    conversion_count = db.Column(db.Integer, default=0, nullable=False)
    last_reset      = db.Column(db.Date, default=date.today, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

pillow_heif.register_heif_opener()
os.makedirs(OUTPUT_DIR, exist_ok=True)


def convert_heic_to_image(file_storage):
    # 1. Seek to beginning in case the FileStorage pointer is anywhere else
    file_storage.stream.seek(0)
    raw_bytes = file_storage.read()
    # 2. Use read_heif with the raw bytes
    heif_file = pillow_heif.read_heif(data=raw_bytes)
    # 3. Convert frombytes based on the mode
    return Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, 'raw')


def convert_image_to_pdf(image):
    img_bytes = io.BytesIO()
    image.save(img_bytes, format='PNG')
    return img2pdf.convert(img_bytes.getvalue())


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
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=6)
    raw = db.session.query(
        func.date(ConversionLog.timestamp), func.count()
    ).filter(
        ConversionLog.user_id==current_user.id,
        ConversionLog.timestamp>=week_ago
    ).group_by(func.date(ConversionLog.timestamp)).all()
    streak = 0
    for i in range(30):
        d = date.today() - timedelta(days=i)
        if ConversionLog.query.filter_by(user_id=current_user.id).filter(func.date(ConversionLog.timestamp)==d).count():
            streak += 1
        else:
            break
    date_map = {str(d):c for d,c in raw}
    days = [(today - timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    chart_data = [date_map.get(d,0) for d in days]
    payments = PaymentHistory.query.filter_by(user_id=current_user.id).order_by(PaymentHistory.date.desc()).all()
    today = datetime.utcnow().date()
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
    # pull the plan’s limit (None → unlimited)
    conversion_limit = current_user.plan.conversion_limit

    # compute remaining (None stays None)
    remaining_today = (
        max(conversion_limit - conversions_today, 0)
        if conversion_limit is not None else
        None
    )
    return render_template(
        'profile.html',
        chart_data=chart_data,
        streak=streak,
        payment_history=payments,
        conversions_today=conversions_today,
        conversions_month=conversions_month,
        conversion_limit=conversion_limit,
        remaining_today=remaining_today,
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
    price_id = sub['items']['data'][0]['price']['id']
    plan_name = 'plus' if price_id == PLUS_PRICE_ID else 'pro'
    plan_obj  = Plan.query.filter_by(name=plan_name).first()

    ends_at = datetime.utcfromtimestamp(sub['current_period_end'])

    amount = sub['items']['data'][0]['price']['unit_amount'] / 100.0

    if not PaymentHistory.query.filter_by(stripe_session_id=session_id).first():
        payment = PaymentHistory(
            user_id=user.id,
            plan=plan_name,
            amount=amount,
            status='succeeded',
            stripe_session_id=session_id
        )
        db.session.add(payment)

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
    
    if event['type'] == 'checkout.session.completed':
        sess = event['data']['object']
        user = User.query.filter_by(stripe_customer_id=sess['customer']).first()
        sub  = stripe.Subscription.retrieve(sess['subscription'])
        if user:
            update_user_subscription(user, sub, sess['id'])

    elif event['type'] == 'invoice.payment_succeeded':
        inv  = event['data']['object']
        sub  = stripe.Subscription.retrieve(inv['subscription'])
        user = User.query.filter_by(stripe_customer_id=sub['customer']).first()
        if user:
            update_user_subscription(user, sub, inv['id'])
    return '', 200


@app.route('/api/remaining_conversions')
def remaining_conversions():
    # logged-in user
    if current_user.is_authenticated:
        today = datetime.utcnow().date()
        used = ConversionLog.query.filter(
            ConversionLog.user_id == current_user.id,
            func.date(ConversionLog.timestamp) == today
        ).count()
        limit = current_user.plan.conversion_limit
    else:
        today = datetime.utcnow().date()
        last_reset = session.get('guest_last_reset')
        if last_reset != today.isoformat():
            session['guest_last_reset']       = today.isoformat()
            session['guest_conversion_count'] = 0
        used  = session.get('guest_conversion_count', 0)
        limit = Plan.query.filter_by(name='free').first().conversion_limit

    return jsonify({
        'remaining': max(limit - used, 0),
        'limit': limit,
        'used': used
    })


@app.route('/convert', methods=['POST'])
def convert():
    # 1. Gather & validate
    files = request.files.getlist('files') or [request.files.get('file')]
    files = [f for f in files if f]
    if not files:
        return "No file uploaded", 400

    # 2. Authenticated vs guest
    if current_user.is_authenticated:
        # row-lock on the user, no explicit begin()
        actor = (
            User.query
                .filter_by(id=current_user.id)
                .with_for_update()
                .first()
        )

        # DAILY RESET
        today = datetime.utcnow().date()
        if actor.last_reset is None or actor.last_reset < today:
            actor.last_reset       = today
            actor.conversion_count = 0

        plan       = actor.plan
        limit      = plan.conversion_limit
        used_today = ConversionLog.query.filter(
            ConversionLog.user_id == actor.id,
            func.date(ConversionLog.timestamp) == today
        ).count()

        # batch only for Pro
        if len(files) > 1 and not plan.batch_allowed:
            return jsonify({'error':'Batch upload is only for Pro.'}), 403

        # daily cap
        if used_today + len(files) > limit:
            return jsonify({'error':'Daily conversion limit reached.'}), 403

        # 3. Convert & log
        outputs, errors = [], []
        fmt = request.form.get('format','jpeg').lower()
        if fmt == 'jpg': fmt = 'jpeg'

        for f in files:
            try:
                # size-limit
                if plan.file_size_limit:
                    f.stream.seek(0, os.SEEK_END)
                    size_mb = f.tell()/(1024*1024)
                    f.stream.seek(0)
                    if size_mb > plan.file_size_limit:
                        raise ValueError(f"{f.filename} exceeds {plan.file_size_limit}MB")

                # HEIC/HEIF?
                lower = f.filename.lower()
                if lower.endswith(('.heic','.heif')):
                    try:
                        f.stream.seek(0)
                        image = Image.open(f); image.load()
                    except:
                        f.stream.seek(0)
                        raw = f.read()
                        heif = pillow_heif.read_heif(data=raw)
                        image = Image.frombytes(heif.mode, heif.size, heif.data, 'raw')
                else:
                    f.stream.seek(0)
                    image = Image.open(f); image.load()

                # ensure RGB/L
                if image.mode not in ('RGB','L'):
                    image = image.convert('RGB')

                # render
                if fmt == 'pdf':
                    data, mime, ext = convert_image_to_pdf(image), 'application/pdf','pdf'
                elif fmt == 'png':
                    buf = io.BytesIO(); image.save(buf,format='PNG')
                    data, mime, ext = buf.getvalue(),'image/png','png'
                elif fmt == 'jpeg':
                    buf = io.BytesIO(); image.save(buf,format='JPEG')
                    data, mime, ext = buf.getvalue(),'image/jpeg','jpg'
                else:
                    raise ValueError(f"Unsupported format: {fmt}")

                name = secure_filename(os.path.splitext(f.filename)[0]) + f".{ext}"
                outputs.append((mime, data, name))

                # log
                db.session.add(ConversionLog(
                    user_id=actor.id,
                    original_filename=secure_filename(f.filename),
                    output_format=fmt
                ))

            except Exception as e:
                errors.append(f"{f.filename}: {e}")

        # commit *all* logs & actor changes together
        db.session.commit()

    else:

        # ─── Guest logic ─────────────────────────────────────────────────
        today_iso = datetime.utcnow().date().isoformat()
        if session.get('guest_last_reset') != today_iso:
            session['guest_last_reset']       = today_iso
            session['guest_conversion_count'] = 0

        used_guest = session.get('guest_conversion_count', 0)
        limit      = 3

        if len(files) > 1:
            return jsonify({'error':'Batch upload only for Pro.'}), 403
        if used_guest + len(files) > limit:
            return jsonify({'error':'Daily conversion limit reached.'}), 403

        outputs, errors = [], []
        fmt = request.form.get('format','jpeg').lower()
        if fmt == 'jpg': 
            fmt = 'jpeg'

        for f in files:
            try:
                f.stream.seek(0)
                image = Image.open(f); image.load()
                if image.mode not in ('RGB','L'):
                    image = image.convert('RGB')

                if fmt == 'pdf':
                    data, mime, ext = convert_image_to_pdf(image), 'application/pdf', 'pdf'
                elif fmt == 'png':
                    buf = io.BytesIO(); image.save(buf, format='PNG')
                    data, mime, ext = buf.getvalue(), 'image/png', 'png'
                elif fmt == 'jpeg':
                    buf = io.BytesIO(); image.save(buf, format='JPEG')
                    data, mime, ext = buf.getvalue(), 'image/jpeg', 'jpg'
                else:
                    raise ValueError(f"Unsupported: {fmt}")

                out_name = secure_filename(os.path.splitext(f.filename)[0]) + f".{ext}"
                outputs.append((mime, data, out_name))

            except Exception as e:
                errors.append(f"{f.filename}: {e}")

        session['guest_conversion_count'] = used_guest + len(outputs)

    # ─── 4. If nothing succeeded ───────────────────────────────────────────
    if not outputs:
        return make_response(jsonify({'errors': errors}), 400)

    # ─── 5. Return single file or a ZIP ───────────────────────────────────
    if len(outputs) == 1:
        mime, data, name = outputs[0]
        resp = send_file(io.BytesIO(data),
                         as_attachment=True,
                         download_name=name,
                         mimetype=mime)
    else:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for mime, data, name in outputs:
                zf.writestr(name, data)
        buf.seek(0)
        resp = send_file(buf,
                         as_attachment=True,
                         download_name='converted_files.zip',
                         mimetype='application/zip')

    # ─── 6. Attach any per-file errors ───────────────────────────────────
    if errors:
        resp.headers['X-Conversion-Errors'] = "; ".join(errors)

    return resp

if __name__ == '__main__':
    with app.app_context():
        default_plans = [
            ('free',  3,   15, False),
            ('plus', 15,   30, True),
            ('pro', 300, None, True),
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
    app.run(host='0.0.0.0', port=80, debug=False)