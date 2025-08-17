import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegistrationForm, SubjectForm, ScheduleForm, ForgotPasswordForm, ResetPasswordForm
from werkzeug.utils import secure_filename
import secrets
import psycopg2
import redis
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import relationship
import smtplib
from email.mime.text import MIMEText
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()  # تحميل المتغيرات البيئية من ملف .env

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')

# إعدادات قاعدة البيانات لـ Render
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    db_url = 'sqlite:///academy.db'

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
csrf = CSRFProtect(app)

# إعدادات البريد الإلكتروني
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# إنشاء مجلد التحميل إذا لم يكن موجوداً
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_class_in_arabic(class_name):
    class_map = {
        'first_intermediate': 'الأول متوسط',
        'second_intermediate': 'الثاني متوسط',
        'third_intermediate': 'الثالث متوسط',
        'fourth_science': 'الرابع علمي',
        'fourth_literature': 'الرابع أدبي',
        'fifth_science': 'الخامس علمي',
        'fifth_literature': 'الخامس أدبي',
        'sixth_science': 'السادس علمي',
        'sixth_literature': 'السادس أدبي'
    }
    return class_map.get(class_name, class_name)

@app.context_processor
def utility_processor():
    return dict(get_class_in_arabic=get_class_in_arabic)

# نماذج قاعدة البيانات
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    student_class = db.Column(db.String(50))
    specialization = db.Column(db.String(100))
    hourly_rate = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text)
    image = db.Column(db.String(100))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    subject = db.relationship('Subject', backref=db.backref('teachers', lazy=True))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_level = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class TeacherCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    used = db.Column(db.Boolean, default=False)
    subject = db.relationship('Subject', backref=db.backref('codes', lazy=True))

class ResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    used = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True))

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_level = db.Column(db.String(50), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    period1 = db.Column(db.String(100))
    period2 = db.Column(db.String(100))
    period3 = db.Column(db.String(100))
    period4 = db.Column(db.String(100))
    period5 = db.Column(db.String(100))
    period6 = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_level = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class AssignmentSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submission_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='submitted')

class Lecture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# المسارات
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            (User.email == form.identifier.data) | 
            (User.username == form.identifier.data)
        ).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('بيانات الدخول غير صحيحة', 'danger')
    return render_template('login.html', form=form)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # توليد رمز مكون من 5 أرقام
            token = secrets.token_hex(3).upper()[:5]
            reset_token = ResetToken(
                user_id=user.id,
                token=token
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # إرسال البريد الإلكتروني
            try:
                msg = MIMEText(f'رمز استعادة كلمة المرور الخاص بك هو: {token}')
                msg['Subject'] = 'استعادة كلمة المرور - أكاديمية الرواد'
                msg['From'] = app.config['MAIL_DEFAULT_SENDER']
                msg['To'] = user.email
                
                with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
                    server.starttls()
                    server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                    server.send_message(msg)
                
                flash('تم إرسال رمز الاستعادة إلى بريدك الإلكتروني', 'success')
            except Exception as e:
                print(f'Error sending email: {e}')
                flash(f'تم توليد الرمز: {token} (في بيئة التطوير)', 'info')
            
            return redirect(url_for('reset_password', email=user.email))
        else:
            flash('البريد الإلكتروني غير مسجل', 'danger')
    return render_template('forgot_password.html', form=form)

@app.route('/reset_password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    form = ResetPasswordForm()
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('البريد الإلكتروني غير صحيح', 'danger')
        return redirect(url_for('forgot_password'))
    
    if form.validate_on_submit():
        # التحقق من صحة الرمز
        reset_token = ResetToken.query.filter_by(
            user_id=user.id,
            token=form.token.data,
            used=False
        ).first()
        
        if reset_token and (datetime.now(timezone.utc) - reset_token.created_at) < timedelta(minutes=30):
            if form.new_password.data == form.confirm_password.data:
                user.set_password(form.new_password.data)
                reset_token.used = True
                db.session.commit()
                flash('تم تحديث كلمة المرور بنجاح', 'success')
                return redirect(url_for('login'))
            else:
                flash('كلمات المرور غير متطابقة', 'danger')
        else:
            flash('رمز الاستعادة غير صحيح أو منتهي الصلاحية', 'danger')
    
    return render_template('reset_password.html', form=form, email=email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
    
    if form.validate_on_submit():
        # التحقق من تطابق كلمات المرور
        if form.password.data != form.confirm_password.data:
            flash('كلمات المرور غير متطابقة', 'danger')
            return render_template('register.html', form=form)
        
        # التحقق من عدم وجود مستخدم بنفس البريد أو اسم المستخدم
        existing_user = User.query.filter(
            (User.email == form.email.data) | 
            (User.username == form.username.data)
        ).first()
        
        if existing_user:
            flash('البريد الإلكتروني أو اسم المستخدم موجود مسبقاً', 'danger')
            return render_template('register.html', form=form)
        
        # التحقق من كود المادة للمدرسين
        if form.user_type.data == 'teacher':
            teacher_code = form.teacher_code.data.strip()
            if not teacher_code:
                flash('يرجى إدخال كود المادة', 'danger')
                return render_template('register.html', form=form)
            
            # البحث عن الكود في قاعدة البيانات
            code_record = TeacherCode.query.filter_by(code=teacher_code).first()
            
            if not code_record:
                flash('كود المادة غير صحيح', 'danger')
                return render_template('register.html', form=form)
                
            if code_record.used:
                flash('كود المادة مستخدم مسبقاً', 'danger')
                return render_template('register.html', form=form)
                
            if code_record.subject_id != form.subject_id.data:
                flash('كود المادة لا يتطابق مع المادة المختارة', 'danger')
                return render_template('register.html', form=form)
            
            # تحديث حالة الكود إلى مستخدم
            code_record.used = True
        
        # معالجة صورة الملف الشخصي
        image_filename = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_filename = filename
        
        # إنشاء المستخدم الجديد
        user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            username=form.username.data,
            user_type=form.user_type.data,
            student_class=form.student_class.data if form.user_type.data == 'student' else None,
            specialization=form.specialization.data if form.user_type.data == 'tutor' else None,
            hourly_rate=form.hourly_rate.data if form.user_type.data == 'tutor' else None,
            subject_id=form.subject_id.data if form.user_type.data == 'teacher' else None,
            image=image_filename
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        # تسجيل الدخول تلقائياً بعد إنشاء الحساب
        login_user(user)
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'student':
        return redirect(url_for('student_dashboard'))
    elif current_user.user_type == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif current_user.user_type == 'owner':
        return redirect(url_for('owner_panel'))
    return render_template('dashboard.html', user=current_user)

@app.route('/owner', methods=['GET', 'POST'])
@login_required
def owner_panel():
    if current_user.user_type != 'owner':
        flash('غير مصرح بالدخول لهذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))
    
    subject_form = SubjectForm()
    schedule_form = ScheduleForm()
    
    if subject_form.validate_on_submit():
        # توليد كود عشوائي للمادة
        subject_code = secrets.token_hex(3).upper()
        new_subject = Subject(
            class_level=subject_form.class_level.data,
            name=subject_form.subject_name.data,
            code=subject_code
        )
        db.session.add(new_subject)
        db.session.commit()
        flash(f'تم إضافة المادة بنجاح - الكود: {subject_code}', 'success')
        return redirect(url_for('owner_panel'))
    
    if schedule_form.validate_on_submit():
        schedule = Schedule(
            class_level=schedule_form.class_level.data,
            day=schedule_form.day.data,
            period1=schedule_form.period1.data,
            period2=schedule_form.period2.data,
            period3=schedule_form.period3.data,
            period4=schedule_form.period4.data,
            period5=schedule_form.period5.data,
            period6=schedule_form.period6.data
        )
        db.session.add(schedule)
        db.session.commit()
        flash('تم حفظ الجدول بنجاح', 'success')
        return redirect(url_for('owner_panel'))
    
    total_students = User.query.filter_by(user_type='student').count()
    total_teachers = User.query.filter_by(user_type='teacher').count()
    total_tutors = User.query.filter_by(user_type='tutor').count()
    
    teachers = User.query.filter_by(user_type='teacher').all()
    tutors = User.query.filter_by(user_type='tutor').all()
    subjects = Subject.query.all()
    schedules = Schedule.query.all()
    teacher_codes = TeacherCode.query.all()
    
    return render_template('owner.html', 
                         subject_form=subject_form,
                         schedule_form=schedule_form,
                         teachers=teachers,
                         tutors=tutors,
                         subjects=subjects,
                         schedules=schedules,
                         teacher_codes=teacher_codes,
                         total_students=total_students,
                         total_teachers=total_teachers,
                         total_tutors=total_tutors)

@app.route('/generate_teacher_code/<int:subject_id>', methods=['POST'])
@login_required
def generate_teacher_code(subject_id):
    if current_user.user_type != 'owner':
        return jsonify({'success': False, 'error': 'غير مصرح بهذا الإجراء'}), 403
    
    subject = db.session.get(Subject, subject_id)
    if not subject:
        return jsonify({'success': False, 'error': 'المادة غير موجودة'}), 404
    
    # توليد كود عشوائي فريد
    code = secrets.token_hex(3).upper()
    
    # التأكد من عدم تكرار الكود
    while TeacherCode.query.filter_by(code=code).first():
        code = secrets.token_hex(3).upper()
    
    # حفظ الكود في قاعدة البيانات
    new_code = TeacherCode(
        code=code,
        subject_id=subject_id,
        used=False
    )
    db.session.add(new_code)
    db.session.commit()
    
    return jsonify({'success': True, 'code': code})

@app.route('/delete_teacher/<int:teacher_id>', methods=['POST'])
@login_required
def delete_teacher(teacher_id):
    if current_user.user_type != 'owner':
        flash('غير مصرح بهذا الإجراء', 'danger')
        return redirect(url_for('dashboard'))
    
    teacher = db.session.get(User, teacher_id)
    if teacher and teacher.user_type in ['teacher', 'tutor']:
        db.session.delete(teacher)
        db.session.commit()
        flash('تم حذف الأستاذ بنجاح', 'success')
    return redirect(url_for('owner_panel'))

@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    if current_user.user_type != 'owner':
        flash('غير مصرح بهذا الإجراء', 'danger')
        return redirect(url_for('dashboard'))
    
    subject = db.session.get(Subject, subject_id)
    if subject:
        # حذف جميع الأكواد المرتبطة بالمادة
        TeacherCode.query.filter_by(subject_id=subject_id).delete()
        
        # حذف المادة
        db.session.delete(subject)
        db.session.commit()
        flash('تم حذف المادة بنجاح', 'success')
    return redirect(url_for('owner_panel'))

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    if current_user.user_type != 'student':
        flash('غير مصرح بالدخول لهذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))
    
    enrolled_courses = Enrollment.query.filter_by(student_id=current_user.id).count()
    completed_assignments = AssignmentSubmission.query.filter_by(
        student_id=current_user.id, 
        status='completed'
    ).count()
    
    upcoming_lectures = Lecture.query.filter(
        Lecture.start_time > datetime.now(timezone.utc),
        Lecture.start_time < datetime.now(timezone.utc) + timedelta(days=7)
    ).count()
    
    institute_teachers = User.query.filter_by(user_type='teacher').limit(5).all()
    private_tutors = User.query.filter_by(user_type='tutor').limit(5).all()
    
    return render_template('student_dashboard.html',
                         enrolled_courses=enrolled_courses,
                         completed_assignments=completed_assignments,
                         upcoming_lectures=upcoming_lectures,
                         institute_teachers=institute_teachers,
                         private_tutors=private_tutors)

@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    if current_user.user_type != 'teacher':
        flash('غير مصرح بالدخول لهذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))
    
    classes = ['first_intermediate', 'second_intermediate', 'third_intermediate',
              'fourth_science', 'fourth_literature', 'fifth_science',
              'fifth_literature', 'sixth_science', 'sixth_literature']
    
    return render_template('teacher_dashboard.html', classes=classes)

@app.route('/teacher_class/<class_level>')
@login_required
def teacher_class(class_level):
    if current_user.user_type != 'teacher':
        flash('غير مصرح بالدخول لهذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))
    
    students = User.query.filter_by(
        user_type='student',
        student_class=class_level
    ).order_by(User.first_name).all()
    
    return render_template('teacher_class.html', 
                          class_level=class_level,
                          students=students)

@app.route('/student_profile/<int:student_id>')
@login_required
def student_profile(student_id):
    student = db.session.get(User, student_id)
    if not student or student.user_type != 'student':
        flash('الطالب غير موجود', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('student_profile.html', student=student)

@app.route('/teacher_profile/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def teacher_profile(teacher_id):
    teacher = db.session.get(User, teacher_id)
    if not teacher or teacher.user_type not in ['teacher', 'tutor']:
        flash('المدرس غير موجود', 'danger')
        return redirect(url_for('student_dashboard'))
    
    # التحقق مما إذا كان الطالب قد قام بتقييم هذا المدرس بالفعل
    already_rated = False
    existing_rating = None
    
    if current_user.is_authenticated and current_user.user_type == 'student':
        existing_rating = Rating.query.filter_by(
            teacher_id=teacher_id,
            student_id=current_user.id
        ).first()
        already_rated = existing_rating is not None
    
    ratings = Rating.query.filter_by(teacher_id=teacher_id).all()
    
    if request.method == 'POST' and not already_rated:
        rating_value = request.form.get('rating')
        comment = request.form.get('comment', '')
        
        if rating_value and rating_value.isdigit():
            rating_value = int(rating_value)
            if 1 <= rating_value <= 5:
                new_rating = Rating(
                    teacher_id=teacher_id,
                    student_id=current_user.id,
                    rating=rating_value,
                    comment=comment
                )
                db.session.add(new_rating)
                
                # تحديث متوسط تقييم المدرس
                ratings = Rating.query.filter_by(teacher_id=teacher_id).all()
                total_ratings = sum(r.rating for r in ratings) + rating_value
                count_ratings = len(ratings) + 1
                teacher.rating = total_ratings / count_ratings
                teacher.rating_count = count_ratings
                
                db.session.commit()
                flash('شكراً لتقييمك!', 'success')
                return redirect(url_for('teacher_profile', teacher_id=teacher_id))
    
    return render_template('teacher_profile.html', 
                          teacher=teacher, 
                          already_rated=already_rated,
                          ratings=ratings)

@app.route('/student_courses')
@login_required
def student_courses():
    if current_user.user_type != 'student':
        return redirect(url_for('dashboard'))
    
    courses = Enrollment.query.filter_by(student_id=current_user.id).all()
    
    return render_template('student_courses.html', courses=courses)

@app.route('/completed_assignments')
@login_required
def completed_assignments():
    if current_user.user_type != 'student':
        return redirect(url_for('dashboard'))
    
    assignments = AssignmentSubmission.query.filter_by(
        student_id=current_user.id, 
        status='completed'
    ).all()
    
    return render_template('completed_assignments.html', assignments=assignments)

@app.route('/upcoming_lectures')
@login_required
def upcoming_lectures():
    if current_user.user_type != 'student':
        return redirect(url_for('dashboard'))
    
    lectures = Lecture.query.filter(
        Lecture.start_time > datetime.now(timezone.utc),
        Lecture.start_time < datetime.now(timezone.utc) + timedelta(days=7)
    ).all()
    
    return render_template('upcoming_lectures.html', lectures=lectures)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(user_type='owner').first():
            owner = User(
                first_name='Owner',
                last_name='Account',
                email=os.environ.get('OWNER_EMAIL', 'owner@academy.com'),
                username='owner',
                user_type='owner'
            )
            owner.set_password(os.environ.get('OWNER_PASSWORD', 'owner_password'))
            db.session.add(owner)
            db.session.commit()
            
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
