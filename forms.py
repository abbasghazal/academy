from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, FloatField, FileField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, ValidationError, Optional

class LoginForm(FlaskForm):
    identifier = StringField('اسم المستخدم أو البريد الإلكتروني', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    submit = SubmitField('تسجيل الدخول')

class RegistrationForm(FlaskForm):
    first_name = StringField('الاسم الأول', validators=[DataRequired()])
    last_name = StringField('الاسم الثاني', validators=[DataRequired()])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=4)])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('تأكيد كلمة المرور', 
                                   validators=[DataRequired(), EqualTo('password', message='كلمات المرور غير متطابقة')])
    user_type = SelectField('نوع الحساب', choices=[
        ('', 'اختر نوع الحساب'),
        ('student', 'طالب'), 
        ('teacher', 'مدرس'), 
        ('tutor', 'مدرس خصوصي')
    ], validators=[DataRequired(message='يرجى اختيار نوع الحساب')])
    
    student_class = SelectField('الصف الدراسي', choices=[
        ('', 'اختر الصف'),
        ('first_intermediate', 'الأول متوسط'),
        ('second_intermediate', 'الثاني متوسط'),
        ('third_intermediate', 'الثالث متوسط'),
        ('fourth_science', 'الرابع علمي'),
        ('fourth_literature', 'الرابع أدبي'),
        ('fifth_science', 'الخامس علمي'),
        ('fifth_literature', 'الخامس أدبي'),
        ('sixth_science', 'السادس علمي'),
        ('sixth_literature', 'السادس أدبي')
    ], validators=[Optional()])
    
    subject_id = SelectField('المادة', coerce=int, choices=[], validators=[Optional()])
    teacher_code = StringField('كود المادة', validators=[Optional()])
    
    specialization = StringField('التخصص', validators=[Optional()])
    hourly_rate = FloatField('السعر بالساعة', 
                           validators=[Optional(), 
                                      NumberRange(min=0, message='يجب أن يكون السعر أكبر من أو يساوي صفر')])
    
    profile_image = FileField('صورة الملف الشخصي')
    
    submit = SubmitField('إنشاء حساب')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False

        if self.user_type.data == 'student' and not self.student_class.data:
            self.student_class.errors.append('يرجى اختيار الصف الدراسي')
            return False

        if self.user_type.data == 'teacher':
            if not self.subject_id.data:
                self.subject_id.errors.append('يرجى اختيار المادة')
                return False
            if not self.teacher_code.data:
                self.teacher_code.errors.append('يرجى إدخال كود المادة')
                return False

        if self.user_type.data == 'tutor':
            if not self.specialization.data:
                self.specialization.errors.append('يرجى إدخال التخصص')
                return False
            if self.hourly_rate.data is None or self.hourly_rate.data < 0:
                self.hourly_rate.errors.append('يرجى إدخال سعر بالساعة صحيح')
                return False

        return True

class SubjectForm(FlaskForm):
    class_level = SelectField('الصف الدراسي', choices=[
        ('first_intermediate', 'الأول متوسط'),
        ('second_intermediate', 'الثاني متوسط'),
        ('third_intermediate', 'الثالث متوسط'),
        ('fourth_science', 'الرابع علمي'),
        ('fourth_literature', 'الرابع أدبي'),
        ('fifth_science', 'الخامس علمي'),
        ('fifth_literature', 'الخامس أدبي'),
        ('sixth_science', 'السادس علمي'),
        ('sixth_literature', 'السادس أدبي')
    ], validators=[DataRequired()])
    subject_name = StringField('اسم المادة', validators=[DataRequired()])
    submit = SubmitField('إضافة المادة')

class ScheduleForm(FlaskForm):
    class_level = SelectField('الصف الدراسي', choices=[
        ('first_intermediate', 'الأول متوسط'),
        ('second_intermediate', 'الثاني متوسط'),
        ('third_intermediate', 'الثالث متوسط'),
        ('fourth_science', 'الرابع علمي'),
        ('fourth_literature', 'الرابع أدبي'),
        ('fifth_science', 'الخامس علمي'),
        ('fifth_literature', 'الخامس أدبي'),
        ('sixth_science', 'السادس علمي'),
        ('sixth_literature', 'السادس أدبي')
    ], validators=[DataRequired()])
    day = SelectField('اليوم', choices=[
        ('sunday', 'الأحد'),
        ('monday', 'الاثنين'),
        ('tuesday', 'الثلاثاء'),
        ('wednesday', 'الأربعاء'),
        ('thursday', 'الخميس')
    ], validators=[DataRequired()])
    period1 = StringField('الحصة الأولى')
    period2 = StringField('الحصة الثانية')
    period3 = StringField('الحصة الثالثة')
    period4 = StringField('الحصة الرابعة')
    period5 = StringField('الحصة الخامسة')
    period6 = StringField('الحصة السادسة')
    submit = SubmitField('حفظ الجدول')

class ForgotPasswordForm(FlaskForm):
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    submit = SubmitField('إرسال رمز الاستعادة')

class ResetPasswordForm(FlaskForm):
    token = StringField('رمز الاستعادة', validators=[DataRequired(), Length(min=5, max=5)])
    new_password = PasswordField('كلمة المرور الجديدة', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('تحديث كلمة المرور')
