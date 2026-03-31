from flask import Flask, jsonify, request
from flask_pymongo import PyMongo
import redis
import os
from bson import ObjectId
import json

app = Flask(__name__)

app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://admin:admin@mongo:27017/DB?authSource=admin')
mongo = PyMongo(app)

redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

tasks_collection = mongo.db.tasks


def task_to_json(task):
    return {
        'id': str(task['_id']),
        'title': task['title'],
        'completed': task.get('completed', False)
    }


@app.route('/tasks', methods=['GET'])
def get_tasks():
    cached_tasks = redis_client.get('all_tasks')
    if cached_tasks:
        return jsonify(json.loads(cached_tasks))
    
    tasks = tasks_collection.find()
    tasks_list = [task_to_json(task) for task in tasks]
    
    redis_client.setex('all_tasks', 30, json.dumps(tasks_list))
    
    return jsonify(tasks_list)

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    
    new_task = {
        'title': data['title'],
        'completed': False
    }
    
    result = tasks_collection.insert_one(new_task)
    
    redis_client.delete('all_tasks')
    
    created_task = tasks_collection.find_one({'_id': result.inserted_id})
    
    return jsonify(task_to_json(created_task)), 201

@app.route('/tasks/<id>', methods=['DELETE'])
def delete_task(id):
    try:
        task_id = ObjectId(id)
    except:
        return jsonify({'error': 'Invalid task id'}), 400
    
    result = tasks_collection.delete_one({'_id': task_id})
    
    if result.deleted_count > 0:
        redis_client.delete('all_tasks')
        return '', 204
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/tasks/<id>', methods=['PUT'])
def update_task(id):
    try:
        task_id = ObjectId(id)
    except:
        return jsonify({'error': 'Invalid task id'}), 400
    
    data = request.json
    
    update_data = {}
    if 'title' in data:
        update_data['title'] = data['title']
    if 'completed' in data:
        update_data['completed'] = data['completed']
    
    result = tasks_collection.update_one(
        {'_id': task_id},
        {'$set': update_data}
    )
    
    if result.modified_count > 0:
        redis_client.delete('all_tasks')
        return jsonify({'message': 'Task updated'}), 200
    
    return jsonify({'error': 'Task not found'}), 404


@app.route('/visits', methods=['GET'])
def visits():
    count = redis_client.incr('visits')
    return jsonify({'visits': count})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)