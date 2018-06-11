import random
import string

from flask import session as login_session

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from database_setup import Base, User, Category
__author__ = 'Sai'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])


# Connect to Database and create database session
engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Adds new user to the database
def create_user(login_session):
    new_user = User(name=login_session['username'],
                    email=login_session['email'],
                    picture=login_session['picture'])
    session.add(new_user)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# Gets user info based on the id
def get_user_info(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


# Gets user id based the email
def get_user_id(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return None


# Checks if the give file has a valid extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


# Lets a list of all the available categories
def get_all_categories():
    categories = session.query(Category).order_by(asc(Category.name))
    return categories


# Checks if the user has logged in
def user_logged_in():
    if 'username' not in login_session:
        return False
    return True


# generates and assigns a csrf token to session
def generate_csrf_token():
    if 'csrf_token' not in login_session:
        login_session['csrf_token'] = ''.join(random.choice
                                              (string.ascii_uppercase +
                                               string.digits)
                                              for x in range(32))
    return login_session['csrf_token']
