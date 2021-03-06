"""
    PlanUp

    An application which helps users planning movies,
    outings,trips with their friends.
"""

from sqlite3 import dbapi2 as sqlite3
from flask import Flask,make_response,g,request
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from pyfcm import FCMNotification
import os,json

app = Flask(__name__)

with open('fcm_api_key','r') as fcm_api_key:
    fcm_key = fcm_api_key.read()
# firebase cloud messaging service to notify users
push_service = FCMNotification(api_key=fcm_key)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'planup.db'),
    DEBUG=True,
    SECRET_KEY='developmentkey',
    USERNAME='admin',
    PASSWORD='default',
    SQLALCHEMY_DATABASE_URI=('sqlite:///' + os.path.join(basedir,'planup.db') + '?check_same_thread=False'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    VERSION='0.0.1'))

db = SQLAlchemy(app)

from models import User,Group

db.create_all()
db.session.commit()

def create_response(response_dict, code=200):
    """Converts dictionary to flask return object"""
    response = make_response(json.dumps(response_dict))
    response.content_type = "application/json"
    return response, code


@app.route('/version')
def version():
    resp = {'version':app.config.get('VERSION')}
    return create_response(resp, 200)

@app.route('/users',methods=['POST'],defaults={'user_id':None})
@app.route('/users/<user_id>',methods=['GET'])
def users(user_id):
    if request.method == 'POST':
        data = request.json.get('data')
        user = User(data.get('user_id'),
                data.get('first_name'),
                data.get('last_name'),
                data.get('profile_url'),
                data.get('fcm_token'))
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            print 'User alredy exists'
            pass
        resp = {"data":{
            "type":"user",
            "id":user.user_id
            }}
        resp_code = 201
    elif request.method == 'GET':
        usr = User.query.filter_by(user_id=user_id).first()
        if usr is not None:
            resp = {"data":usr.as_dict()}
            resp_code = 200
        else:
            resp = {"data":""}
            resp_code = 404
    return create_response(resp,resp_code)

@app.route('/users/<user_id>/groups',methods=['GET'])
def user_groups(user_id):
    usr = User.query.filter_by(user_id=user_id).first()
    group_list = []
    resp ={"type":"usergroup"}
    if usr is not None:
        for grp in usr.user_group:
            group_list.append(grp.as_dict()) 
    resp["data"]=group_list
    return make_response(json.dumps(resp)),200

@app.route('/groups/<group_id>',methods=['GET','PUT','DELETE'])
@app.route('/groups',methods=['POST'],defaults={'group_id':None})
def groups(group_id):
    if request.method == 'GET':
        group = Group.query.filter_by(group_id=group_id).first()
        if group is not None:
            data = {'group_id':group.group_id,
                    'group_name':group.group_name,
                    'member_count':group.count,
                    'type':'group'}
            usr_list = []
            for usr in group.users:
                usr_dict = {'user_id':usr.user_id,
                        'first_name':usr.first_name,
                        'last_name':usr.last_name}
                usr_list.append(usr_dict)
            data['members']=usr_list
        return make_response(json.dumps({"data":data})),200
    elif request.method == 'POST':
        data = request.json.get('data')
        usr_list = data.get('users')
        group = Group(data.get('name'),data.get('count'))
        try:
            db.session.add(group)
            db.session.commit()
        except IntegrityError:
            pass
        registration_ids = []
        for usr in usr_list:
            mUser = User.query.filter_by(
                    user_id=usr['user_id']).first()
            mUser.user_group.append(group)
            registration_ids.append(mUser.fcm_token)
        db.session.commit()
        resp = {'data':{
            'type':'group',
            'id':group.group_id}}
        resp_code = 201
        # notify users
        message_title = "PlanUp"
        message_body = "You've been added to "+group.group_name
        # result = push_service.notify_multiple_devices(registration_ids=registration_ids,
                # message_title=message_title, message_body=message_body)

    elif request.method == 'DELETE':
        Group.delete.filter_by(group_id=group_id)
        resp = {"data":""}
        resp_code = 200
    return create_response(resp,resp_code)
