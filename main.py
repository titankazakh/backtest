import json
import plotly
import plotly.express as px
import yfinance as yf
import pandas as pd
import pandas_datareader as web
import numpy as np
import matplotlib
import lxml
import requests
import pandas_datareader
import datetime
import pandas_datareader.data as web
import plotly.graph_objects as go
from datetime import datetime, timedelta
from flask import Flask
from flask import redirect, url_for
from flask import render_template
from flask import request, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config[
        'SQLALCHEMY_DATABASE_URI'] = r'sqlite:///C:\Users\User\PycharmProjects\pythonProject2/projectdb.db'

app.config['SECRET_KEY'] = "my secret key here"

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)  # integer primary key will be autoincremented by default
    login = db.Column(db.String(255), unique=True, nullable=False)
    user_fname = db.Column(db.String(255))
    user_sname = db.Column(db.String(255))
    password = db.Column(db.String(255), nullable=False)

    user_CVs = db.relationship("CVs", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"User(user_id {self.user_id!r}, name={self.user_fname!r}, surname={self.user_fname!r})"

class CVs(db.Model):
    __tablename__ = "CVs"
    cv_id = db.Column(db.Integer, primary_key=True)  # integer primary key will be autoincremented by default
    cv_data = db.Column(db.String(255), nullable=False)
    stock_weight = db.Column(db.Float(255), nullable=False)
    cv_owner = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    owner = db.relationship("User", back_populates="user_CVs")

    def __repr__(self) -> str:
        return f"CVs(cv_id={self.cv_id!r}, cv_data={self.cv_data!r}, owner={self.cv_owner!r})"
def add_user(user:User)->None:
    db.session.add(user)
    db.session.commit()

def delete_user(user:User)->None:
    db.session.delete(user)
    db.session.commit()

def get_all_users()->db.Query:
    return User.query.all()




@app.route('/')

def home():
    #db.create_all()
    if session.__len__() > 1 and session['uid']:
        return render_template('home.html', context = session['uid'])

    return render_template('home.html')

@app.route('/stocks')
def stocks():
    if session.__len__() > 1 and session['uid']:

        return render_template('stocks.html', context = session['uid'])

    return render_template('stocks.html')

@app.route('/stocks/callback/<endpoint>')
def cb(endpoint):
    if endpoint == "getStock":
        return getstock(request.args.get('data'), request.args.get('period'), request.args.get('interval'))





def getstock(stock, period, interval):
    st = yf.Ticker(stock)

    df = st.history(period=(period), interval=interval)
    df = df.reset_index()
    df.columns = ['Date-Time'] + list(df.columns[1:])
    max = (df['Open'].max())
    min = (df['Open'].min())
    range = max - min
    margin = range * 0.05
    max = max + margin
    min = min - margin
    fig = px.area(df, x='Date-Time', y="Open",
                  hover_data=("Open", "Close", "Volume"),
                  range_y=(min, max), template="seaborn")


    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON



@app.route("/about")
def about(context=None):
    return render_template("about.html", context=context)


@app.route('/logout')
def logout():
    if session.__len__() > 1:
        session.pop('authenticated', None)
        session.pop('uid')
        session.pop('username')
        session.pop('password')
    return redirect(url_for('login'))

@app.route("/user/<int:user_id>", methods=['GET', 'POST'])
def user_page(user_id, context=None):
    if user_id == 0 or user_id != session['uid']:
        return redirect(url_for('login'))

    if request.method == "POST":
        db.session.add(CVs(cv_data=request.form['data'],
                           stock_weight=request.form['stock_weight'],
                           cv_owner=user_id))
        db.session.commit()
    query = db.session.query(User).join(CVs).filter(CVs.cv_owner == user_id).first()
    if query:
        return render_template("display user portfolio.html", context=query)
    else:
        query = db.session.query(User).filter(User.user_id == user_id).first()
        return render_template("display user portfolio.html", context=query)
@app.route('/user/<int:user_id>/callback/<endpoint>')
def callback(endpoint,user_id):
    if endpoint == "getStock":
        return gets( request.args.get('period'),  request.args.get('user_id'), request.args.get('index'))



def gets(period, user_id, index):
    print()
    init_investment = 10000

    start = datetime.now() - timedelta(days = int(period))
    end = datetime.now()
    SPY = web.DataReader(index, 'yahoo', start, end)
    SPY['Cum Return'] = SPY['Adj Close'] / SPY.iloc[0]['Adj Close']
    SPY['SPY Total'] = init_investment * SPY['Cum Return']
    SPY['SPY Total'] = round(SPY['SPY Total'])
    query = db.session.query(User).join(CVs).filter(CVs.cv_owner == user_id).first()
    StockList = []
    allocation_pct = []
    columns = []
    for i in query.user_CVs:
        StockList.append(web.DataReader(i.cv_data,'yahoo',start, end))
        allocation_pct.append(i.stock_weight)
        columns.append(i.cv_data)
    for df in StockList:
        df['Cum Return'] = df['Adj Close'] / df.iloc[0]['Adj Close']


    for df, alloc in zip(StockList, allocation_pct):
        df['Value'] = alloc * init_investment * df['Cum Return']

    all_vals = []
    for i in StockList:
        all_vals.append(i['Value'])
    portfolio_val = pd.concat(all_vals, axis=1)
    portfolio_val.columns = columns


    portfolio_val['Portfolio Total'] = round(portfolio_val.sum(axis=1))
    portfolio_val['Cum Return'] = portfolio_val['Portfolio Total'] / portfolio_val.iloc[0]['Portfolio Total']
    portfolio_val['Cum Return %'] = (portfolio_val['Cum Return'] - 1) * 100
    SPY['Cum Return %'] = (SPY['Cum Return'] - 1) * 100
    SPY.tail()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=portfolio_val.index, y=portfolio_val['Cum Return %'], name='Portfolio Cumulative Return %'))
    fig.add_trace(go.Scatter(x=SPY.index, y=SPY['Cum Return %'], name='Index Cumulative Return %'))
    fig.update_layout(title="Cumulative Return % (Portfolio vs Index)")

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

@app.route("/delete_stock/<int:stock_id>/<int:user_id>", methods=['GET', 'POST'])
def delete_stock(stock_id,user_id, context=None):

    stockToDelete = CVs.query.filter_by(cv_id = stock_id).first()
    db.session.delete(stockToDelete)
    db.session.commit()
    return redirect(url_for("user_page", user_id=user_id))

@app.route('/register', methods =['GET', 'POST'])
def register(context=None):

    if request.method == "POST":
        login = request.form['username']
        fname = request.form['fname']
        sname = request.form['sname']
        pass1 = request.form['password']
        pass2 = request.form['password_conf']

        data = db.session.query(User).filter_by(login=request.form['username']).first()

        if data:
            return redirect(url_for("register", error="Already registered!"))
        elif pass1 != pass2:
            return redirect(url_for("register", error="Passowords do not match!"))
        else:
            add_user(User(login=login,
                          user_fname=fname,
                          user_sname=sname,
                          password=pass1))

            return redirect(url_for("login", context="Succesfully registered!"))
    if session.__len__() > 1 and session['uid']:
        return render_template("register.html", context=session['uid'])
    return render_template("register.html")



@app.route("/login", methods = ["GET", "POST"])
def login(context=None):
    if request.method == "POST":
        user = db.session.query(User).filter_by(login=request.form['username'], password=request.form['password']).first()
        print(user)
        if user:
            session['authenticated'] = True
            session['uid'] = user.user_id
            session['username'] = user.login
            session['password'] = user.password
            return redirect(url_for("user_page", user_id=user.user_id))
        else:
            if session.__len__() > 1 and session['uid']:
                return render_template("login.html", context=session['uid'])
            return render_template("login.html")
    if session.__len__() > 1 and session['uid']:
        return render_template("login.html", context=session['uid'])
    return render_template("login.html")


@app.route("/change_user_cv/<int:user_id>", methods = ["GET", "POST"])
def change_user_cv(user_id, context=None):
    if request.method == "POST":
        db.session.add(CVs(cv_data = request.form['data'],
                           stock_weight = request.form['stock_weight'],
                           cv_owner = user_id))
        db.session.commit()

    return render_template("change user cv.html", context=user_id)

#if __name__ == "__main__":

app.run(port = 5000, debug=False)


