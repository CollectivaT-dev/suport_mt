from pymongo import MongoClient

task_taker_dict = {} #task_id: taker username  (None if not taken)
task_requestmessage_dict = {} #task_id:task_message
task_originalmessage_dict = {} #task_id:original_message
task_submission_dict = {} #task_id:translation_submission_message

class TasksDB(object):
    def __init__(self, db_name='suportmutu', collection_name=None):
        if not collection_name:
            raise ValueError("collection name not given for TasksDB")
        self.db_name = db_name
        self.collection_name = collection_name
        self.q_nontranslated = {'$or': [{'translated': False},
                                        {'translated': {'$exists': False}}]}

    def connect(self):
        # TODO check docker network connection
        client = MongoClient('localhost',  27017)
        self.db = client[self.db_name]
        self.collection = self.db[self.collection_name]

    def insert_task(self, task):
        if task.get('_id'):
            self.update_taks(task)
        else:
            # check last id
            #new_task_id = get_max_task_id()+1
            task['_id'] = self.get_max_task_id()+1
            self.collection.insert_one(task)
        return task['_id']

    def update_task(self, task):
        res = self.collection.replace_one({"_id":task["_id"]},
                                          task,
                                          upsert=True)

    def get_max_task_id(self):
        last_id = 1
        for task in self.collection.find().sort("_id", -1):
            last_id = task['_id']
            break
        return last_id

    def get(self, task_id):
        ref = self.collection.find_one({'_id': task_id})
        if ref:
            return ref
        else:
            return None

    def get_nontranslated(self, task_id):
        ref = self.collection.find_one({"$and":[{"_id": task_id},
                                                self.q_nontranslated]})
        if ref:
            return ref
        else:
            return None

    def get_nontranslated_of_user(self, username):
        ref = self.collection.find_one({"$and":[self.q_nontranslated,
                                                {"task_taker": username}]})
        if ref:
            return ref
        else:
            return None

    def get_active_tasks(self):
        ref = self.collection.find({"$and": [{"task_taker":{'$ne':None}},
                                             self.q_nontranslated]})
        return ref

    def get_passive_tasks(self):
        ref = self.collection.find({"$and":[self.q_nontranslated,
                                            {"task_taker":None}]})
        return ref

    def get_nontranslated_tasks(self):
        ref = self.collection.find({"$or":[self.q_nontranslated,
                                         {"translated": {"$exists": False}}]})
        return ref

    def get_nontranslated_submitted_tasks(self, username):
        ref = self.collection.find({"$and":[self.q_nontranslated,
                                            {"task_taker": username},
                                            {"submission": {"$exists":True}}]})
        return ref 
