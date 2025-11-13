from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 创建数据库对象
db = SQLAlchemy(app)

# 定义用户数据模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')

# 定义图书数据模型
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(30), default='未分类')
    status = db.Column(db.String(20), default='在馆')
    borrow_count = db.Column(db.Integer, default=0)

# 定义借阅历史记录模型
class BorrowHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    book_title = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# 定义评论数据模型
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    timestamp = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# 定义意见反馈模型
class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    status = db.Column(db.String(20), default='未处理')

# 初始化数据库
def init_db():
    with app.app_context():
        # 删除所有表（如果存在）
        db.drop_all()
        # 创建所有表
        db.create_all()
        
        print("数据库表创建完成")
        
        # 创建默认管理员账户
        admin_user = User(
            username='ABC',
            password=generate_password_hash('ABC123'),
            role='admin'
        )
        db.session.add(admin_user)
        
        # 创建默认普通用户
        normal_user = User(
            username='abc',
            password=generate_password_hash('abc123'),
            role='user'
        )
        db.session.add(normal_user)
        
        # 添加示例图书
        sample_books = [
            Book(title='红楼梦', author='曹雪芹', category='文学'),
            Book(title='三体', author='刘慈欣', category='科幻'),
            Book(title='人类简史', author='尤瓦尔·赫拉利', category='历史'),
            Book(title='Python编程', author='John Smith', category='科技')
        ]
        db.session.add_all(sample_books)
        
        db.session.commit()
        print("默认数据添加完成")
        print("管理员账户: ABC / ABC123")
        print("普通用户账户: abc / abc123")

# 登录检查装饰器
def login_required(role='user'):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('请先登录', 'error')
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user:
                flash('用户不存在', 'error')
                return redirect(url_for('login'))
            
            if role == 'admin' and user.role != 'admin':
                flash('需要管理员权限', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 首页
@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        
        total_books = Book.query.count()
        available_books = Book.query.filter_by(status='在馆').count()
        borrowed_books = Book.query.filter_by(status='已借出').count()
        
        popular_books = Book.query.order_by(Book.borrow_count.desc()).limit(5).all()
        
        return render_template('index.html', 
                             user=user,
                             total_books=total_books,
                             available_books=available_books,
                             borrowed_books=borrowed_books,
                             popular_books=popular_books)
    else:
        return redirect(url_for('login'))

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'欢迎回来，{username}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('register.html')
        
        # 添加密码格式验证
        if len(password) < 6:
            flash('密码长度至少需要6位', 'error')
            return render_template('register.html')
        
        # 检查密码是否只包含字母和数字
        if not re.match("^[A-Za-z0-9]*$", password):
            flash('密码只能包含字母和数字', 'error')
            return render_template('register.html')
        
        # 检查用户名是否只包含字母和数字
        if not re.match("^[A-Za-z0-9]*$", username):
            flash('用户名只能包含字母和数字', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('register.html')
        
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            role='user'
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# 注销
@app.route('/logout')
def logout():
    session.clear()
    flash('已成功注销', 'success')
    return redirect(url_for('login'))

# 修改密码
@app.route('/change_password', methods=['GET', 'POST'])
@login_required()
def change_password():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # 验证当前密码
        if not check_password_hash(user.password, current_password):
            flash('当前密码错误', 'error')
            return render_template('change_password.html', user=user)
        
        # 验证新密码格式
        if len(new_password) < 6:
            flash('新密码长度至少需要6位', 'error')
            return render_template('change_password.html', user=user)
        
        # 检查新密码是否只包含字母和数字
        if not re.match("^[A-Za-z0-9]*$", new_password):
            flash('新密码只能包含字母和数字', 'error')
            return render_template('change_password.html', user=user)
        
        # 确认新密码
        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'error')
            return render_template('change_password.html', user=user)
        
        # 更新密码
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        flash('密码修改成功', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html', user=user)

# 显示所有图书
@app.route('/books')
@login_required()
def books():
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    
    # 基础查询
    if search_query:
        book_list = Book.query.filter(
            (Book.title.contains(search_query)) | 
            (Book.author.contains(search_query))
        )
    else:
        book_list = Book.query
    
    # 分类筛选
    if category_filter:
        book_list = book_list.filter_by(category=category_filter)
    
    book_list = book_list.all()
    
    # 获取所有分类（用于筛选下拉框）
    categories = db.session.query(Book.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    # 获取每本书的评论和平均评分
    books_with_ratings = []
    for book in book_list:
        comments = Comment.query.filter_by(book_id=book.id).all()
        avg_rating = 0
        if comments:
            avg_rating = sum(comment.rating for comment in comments) / len(comments)
        
        books_with_ratings.append({
            'book': book,
            'avg_rating': round(avg_rating, 1),
            'comment_count': len(comments)
        })
    
    user = User.query.get(session['user_id'])
    
    # 计算用户当前借阅数量
    borrowed_count = BorrowHistory.query.filter_by(user_id=user.id, action='借阅').count()
    returned_count = BorrowHistory.query.filter_by(user_id=user.id, action='归还').count()
    current_borrowed_count = borrowed_count - returned_count
    
    return render_template('books.html', 
                         user=user,
                         books_with_ratings=books_with_ratings, 
                         search_query=search_query,
                         categories=categories,
                         selected_category=category_filter,
                         current_borrowed_count=current_borrowed_count)

# 添加新书（仅管理员）- 单本添加
@app.route('/add_book', methods=['GET', 'POST'])
@login_required('admin')
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        category = request.form['category']
        
        new_book = Book(title=title, author=author, category=category)
        db.session.add(new_book)
        db.session.commit()
        
        flash('图书添加成功', 'success')
        return redirect(url_for('books'))
    
    user = User.query.get(session['user_id'])
    return render_template('add_book.html', user=user)

# 批量添加图书页面（仅管理员）
@app.route('/batch_add_books', methods=['GET', 'POST'])
@login_required('admin')
def batch_add_books():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        book_data = request.form['book_data']
        lines = book_data.strip().split('\n')
        added_count = 0
        error_lines = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # 解析每行数据，格式：书名,作者,分类
            parts = line.split(',')
            if len(parts) < 2:
                error_lines.append(f"第{i}行格式错误：{line}")
                continue
                
            title = parts[0].strip()
            author = parts[1].strip()
            category = parts[2].strip() if len(parts) > 2 else '未分类'
            
            if not title or not author:
                error_lines.append(f"第{i}行错误：书名和作者不能为空")
                continue
            
            # 检查图书是否已存在
            existing_book = Book.query.filter_by(title=title, author=author).first()
            if existing_book:
                error_lines.append(f"第{i}行跳过：图书《{title}》已存在")
                continue
            
            # 添加新书
            new_book = Book(title=title, author=author, category=category)
            db.session.add(new_book)
            added_count += 1
        
        db.session.commit()
        
        if error_lines:
            flash_message = f'成功添加 {added_count} 本图书，但有错误：<br>' + '<br>'.join(error_lines)
            flash(flash_message, 'warning')
        else:
            flash(f'成功批量添加 {added_count} 本图书', 'success')
        
        return redirect(url_for('books'))
    
    return render_template('batch_add_books.html', user=user)

# 借书功能
@app.route('/borrow/<int:book_id>')
@login_required()
def borrow_book(book_id):
    book = Book.query.get(book_id)
    user = User.query.get(session['user_id'])
    
    # 检查用户当前借阅数量
    borrowed_count = BorrowHistory.query.filter_by(user_id=user.id, action='借阅').count()
    returned_count = BorrowHistory.query.filter_by(user_id=user.id, action='归还').count()
    current_borrowed_count = borrowed_count - returned_count
    
    if current_borrowed_count >= 3:
        flash('您已借阅3本书，请归还部分书籍后再借阅新书', 'error')
        return redirect(url_for('books'))
    
    if book and book.status == '在馆':
        book.status = '已借出'
        book.borrow_count += 1
        
        history = BorrowHistory(
            user_id=user.id,
            book_id=book.id,
            book_title=book.title,
            action='借阅'
        )
        db.session.add(history)
        
        db.session.commit()
        flash(f'成功借阅《{book.title}》', 'success')
    else:
        flash('图书不存在或已被借出', 'error')
    
    return redirect(url_for('books'))

# 还书功能
@app.route('/return/<int:book_id>')
@login_required()
def return_book(book_id):
    book = Book.query.get(book_id)
    user = User.query.get(session['user_id'])
    
    if book and book.status == '已借出':
        book.status = '在馆'
        
        history = BorrowHistory(
            user_id=user.id,
            book_id=book.id,
            book_title=book.title,
            action='归还'
        )
        db.session.add(history)
        
        db.session.commit()
        flash(f'成功归还《{book.title}》', 'success')
    else:
        flash('图书不存在或不在借出状态', 'error')
    
    return redirect(url_for('books'))

# 删除图书功能（仅管理员）
@app.route('/delete/<int:book_id>')
@login_required('admin')
def delete_book(book_id):
    book = Book.query.get(book_id)
    
    if book:
        Comment.query.filter_by(book_id=book.id).delete()
        db.session.delete(book)
        db.session.commit()
        flash('图书删除成功', 'success')
    
    return redirect(url_for('books'))

# 图书详情页
@app.route('/book/<int:book_id>')
@login_required()
def book_detail(book_id):
    book = Book.query.get(book_id)
    user = User.query.get(session['user_id'])
    
    if not book:
        flash('图书不存在', 'error')
        return redirect(url_for('books'))
    
    comments = Comment.query.filter_by(book_id=book_id).order_by(Comment.id.desc()).all()
    
    avg_rating = 0
    if comments:
        avg_rating = sum(comment.rating for comment in comments) / len(comments)
    
    return render_template('book_detail.html', 
                         user=user,
                         book=book, 
                         comments=comments,
                         avg_rating=round(avg_rating, 1))

# 添加评论
@app.route('/add_comment/<int:book_id>', methods=['POST'])
@login_required()
def add_comment(book_id):
    content = request.form['content']
    rating = int(request.form['rating'])
    user = User.query.get(session['user_id'])
    book = Book.query.get(book_id)
    
    if not book:
        flash('图书不存在', 'error')
        return redirect(url_for('books'))
    
    new_comment = Comment(
        user_id=user.id,
        username=user.username,
        book_id=book_id,
        content=content,
        rating=rating
    )
    
    db.session.add(new_comment)
    db.session.commit()
    
    flash('评论发表成功', 'success')
    return redirect(url_for('book_detail', book_id=book_id))

# 删除评论（仅管理员）
@app.route('/delete_comment/<int:comment_id>')
@login_required('admin')
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    
    if comment:
        book_id = comment.book_id
        db.session.delete(comment)
        db.session.commit()
        flash('评论删除成功', 'success')
        return redirect(url_for('book_detail', book_id=book_id))
    
    flash('评论不存在', 'error')
    return redirect(url_for('books'))

# 借阅历史页面
@app.route('/history')
@login_required()
def history():
    user = User.query.get(session['user_id'])
    
    if user.role == 'admin':
        history_list = BorrowHistory.query.order_by(BorrowHistory.id.desc()).limit(100).all()
    else:
        history_list = BorrowHistory.query.filter_by(user_id=user.id).order_by(BorrowHistory.id.desc()).limit(50).all()
    
    return render_template('history.html', user=user, history_list=history_list)

# 意见反馈页面
@app.route('/suggestions', methods=['GET', 'POST'])
@login_required()
def suggestions():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        content = request.form['content']
        
        new_suggestion = Suggestion(
            user_id=user.id,
            username=user.username,
            content=content
        )
        
        db.session.add(new_suggestion)
        db.session.commit()
        
        flash('意见提交成功，感谢您的反馈！', 'success')
        return redirect(url_for('suggestions'))
    
    if user.role == 'admin':
        suggestions_list = Suggestion.query.order_by(Suggestion.id.desc()).all()
    else:
        suggestions_list = Suggestion.query.filter_by(user_id=user.id).order_by(Suggestion.id.desc()).all()
    
    return render_template('suggestions.html', user=user, suggestions_list=suggestions_list)

# 处理意见（仅管理员）
@app.route('/handle_suggestion/<int:suggestion_id>/<action>')
@login_required('admin')
def handle_suggestion(suggestion_id, action):
    suggestion = Suggestion.query.get(suggestion_id)
    
    if suggestion:
        if action == 'resolve':
            suggestion.status = '已处理'
            db.session.commit()
            flash('意见已标记为已处理', 'success')
        elif action == 'delete':
            db.session.delete(suggestion)
            db.session.commit()
            flash('意见已删除', 'success')
    
    return redirect(url_for('suggestions'))

# 重置数据库路由（仅在开发时使用）
@app.route('/reset_db')
def reset_db():
    init_db()
    return '数据库已重置！默认账户：<br>管理员: ABC / ABC123<br>普通用户: abc / abc123'

if __name__ == '__main__':
    # 检查数据库是否存在，如果不存在则初始化
    if not os.path.exists('library_system.db'):
        print("初始化数据库...")
        init_db()
    
    app.run(debug=True, host='0.0.0.0', port=5000)