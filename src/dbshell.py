import psycopg2
import psycopg2.pool as pool
import sys
import string
import time
from contextlib import contextmanager
import settings

class database(object):
    """
    This class is for the database connection and data management for the bot.
    
    _conn_string = the connection string used to connect to teh database.  
                   Pulls the password from the settings.py file
    db = the connection pool used by the cursors to query the database
    
    """
    def __init__(self):
        #Define our connection string
        self._conn_string = "host='localhost' dbname='meekbot' user='postgres' password='" + settings.dbpassword + "'"

        # print the connection string we will use to connect
        print("Connecting to database\n    ->%s" % (self._conn_string))

        # get a connection pool, if a connect cannot be made an exception will be raised here
        self.db = pool.SimpleConnectionPool(1, 5, self._conn_string)

    # Get Cursor
    @contextmanager
    def get_cursor(self):
        """Used in contexts inside of other functions to connect to the database,
        get the cursor, and commit changes and close the connection """
        
        self.con = self.db.getconn()
        try:
            yield self.con.cursor()
        finally:
            self.con.commit()
            self.db.putconn(self.con)
    
    def check_stream(self, streamName):
        """Checks to see if the stream already exists in the database.  If not
        a value in the database return a 0.
        
        Paramters:
            streamName - String value of the stream in the meekbot.stream table
        
        Return:
            streamID - ID value from meekbot.stream if exists.  If not return 0
                       -1 if error occured
                       0 if not found
        """
        streamID = 0
        try:
            sql = """SELECT stream_id, stream_name FROM meekbot.stream WHERE stream_name = '{}' and active_ind = true;"""
            print(sql.format(streamName))
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(streamName))
                if cursor.rowcount > 0:
                    record = cursor.fetchone()
                    print(record)
                    streamID = record[0]
                    print(streamID)

        except:
            print("Failed checking for stream in dbshell.checkStream")
            streamID = -1 #return a negative value so that the script knows that the query failed

        return streamID
    
    
    def add_stream(self, streamName):
        """Adds a stream to the meekbot.stream table and returns the streams id
        
        Paramters:
            streamName - String value of stream being added to meekbot.stream
        
        Return:
            streamID - ID number generated during insert
                       -1 if an error occured
        """
        streamID = 0
        try:
            sql = """INSERT INTO meekbot.stream(stream_name, create_dt_tm) VALUES ('{}', {}) RETURNING stream_id;"""
            #print(sql.format(streamName,'now()'))# value_list)
            
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(streamName,'now()'))
                streamID = cursor.fetchone()[0]
                print('Stream ID = ' + str(streamID))
        except:
            print("Failed adding new stream in dbshell.addStream")
            streamID = -1 #return a negative value so that the script knows that the query failed

        return streamID

    def get_person_id(self, viewerName):
        """Gets the viewer's person ID from meekbot.person table and returns it
        
        Paramters:
            viewerName - String value of viewer's username being pulled from meekbot.person
        
        Return:
            personID - ID number of the viewer if found in the datbase
                       -1 if an error occured
                       0 if not found
        """
        personID = 0
        try:
            sql = """SELECT person_id, username FROM meekbot.person WHERE username = '{}' and active_ind = true;"""
            #print(sql.format(viewerName))
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(viewerName))
                if cursor.rowcount > 0:
                    record = cursor.fetchone()
                    print(record)
                    personID = record[0]
                    print(personID)
        except:
            print("Failed getting person_id in dbshell.getPersonID")
            personID = -1 #return a negative value so that the script knows that the query failed

        return personID
    
    def add_person(self, viewerName, streamID, reltn):
        """Adds a viewer to the meekbot.person table and returns the streams id
           Also adds an entry into the person_stream_reltn table containing the
           viewer's relationship to the stream (mod, viewer, admin, etc...).
           
           Use's a stored procedure inside of PostgreSQL to do the insertions.
        
        Paramters:
            viewerName - String of username being added to meekbot.person
            streamID - Stream ID of active stream from meekbot.stream table
            reltn - Viewer's relationship to the stream.  
                    reltn string value comes from meekbot.code_value table 
                    for person_stream_reltn type (code_set = 1)
                    
        
        Return:
            personID - ID number generated during insert
                       -1 if an error occured
        """
        personID = 0
        try:
            sql = """SELECT * FROM meekbot.addperson('{}', {}, '{}')"""
            print(sql.format(viewerName,streamID, reltn.upper()))
            
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(viewerName,streamID, reltn.upper()))
                personID = cursor.fetchone()[0]
                print('Person ID = ' + str(personID))
        except:
            print("Failed adding person_id in dbshell.addPerson")
            personID = -1 #return a negative value so that the script knows that the query failed

        return personID
    
    def update_person_stream_reltn(self, personID, streamID, reltn):
        """Update's a viewer's relationship to the given stream.  Also will add
           a relationship if one does not already exist between person and
           stream
           
           Use's a stored procedure inside of PostgreSQL to do the 
           updates/insertions.
        
        Paramters:
            personID - Viewer's ID from meekbot.person
            streamID - Stream ID of active stream from meekbot.stream table
            reltn - Viewer's relationship to the stream.  
                    reltn string value comes from meekbot.code_value table 
                    for person_stream_reltn type (code_set = 1)
        """
        sql = """SELECT * FROM meekbot.updatePersonStreamReltn({}, {}, '{}')"""
    
        try:           
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(personID,streamID, reltn.upper()))

        except:
            print("Failed updating relationship in dbshell.updatePersonStreamReltn")
            
    def get_stream_reward_info(self,stream_id):
        """Get a stream's reward information from the database.  Includes
           reward point name, rate, duration between gain, and duration unit
        
        Paramters:
            stream_id - Stream ID of active stream from meekbot.stream table

        Returns: List of results in the following order:
                - Point Name
                - Reward Rate (number of points)
                - Reward Rate Duration (Time between reward increase)
                - Reward Rate Duration Unit (Time unit of reward rate)
                OR
                - "None" if no rewards found
        """        
        sql = """SELECT stream_reward.point_name ,stream_reward.reward_rate 
                 ,stream_reward.reward_dur,code_value.display
           FROM meekbot.stream_reward
                JOIN meekbot.code_value ON code_value.code_value = stream_reward.reward_dur_unit_cd
            WHERE stream_reward.stream_id = {}
            AND stream_reward.active_ind = true
            AND code_value.active_ind = true"""
            
        try:           
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(stream_id))
                if cursor.rowcount > 0:
                    record = cursor.fetchone()
                else:
                    record = "None"
        except:
            print("Failed getting reward info from dbshell.get_stream_reward_info")
        
        return record
    
    def get_person_stream_rewards(self, stream_id, person_id):
        """Gets the number of reward points a viewer has for the current stream
           If user does not exist in person_stream_reward table it adds them
        
            Parameters:
                stream_id = id of the stream from the meekbot.stream table
                person_id = id of the viewer from the meekbot.person table
            Returns:
                Quantity of reward points from meekbot.person_stream_reward
        """
        insert_viewer_flg = 0
        reward_pts = 0 #if no row found than return 0 points
        sql = """SELECT qty FROM meekbot.person_stream_reward 
                 WHERE stream_id = {} AND person_id = {} and active_ind = true;"""
            
        try:           
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(stream_id, person_id))
                if cursor.rowcount > 0:
                    record = cursor.fetchone()
                    reward_pts = record[0]
                    print('Reward = ' + str(reward_pts))
                else:
                    insert_viewer_flg = 1
        except:
            print("Failed getting reward points from dbshell.get_person_stream_rewards")
        
        #If the user doesn't exist in the table add them and return 0 qty
        if insert_viewer_flg == 1:
            sql = """INSERT INTO meekbot.person_stream_reward(stream_id
                                                            ,person_id
                                                            ,qty,create_dt_tm) 
                    VALUES ({}, {}, 0, now());"""
            
            try:           
                with self.get_cursor() as cursor:
                    cursor.execute(sql.format(stream_id, person_id))
            except:
                print("Failed inserting viewr in dbshell.get_person_stream_rewards")
        
        return reward_pts
    
    def update_user_rewards(self, stream_id, person_id, reward_pts):
        """ Updates the amount of reward points for a user/stream combination
            in the meekbot.person_stream_reward table
            
            Parameters:
                stream_id = The stream id from meekbot.stream to which the
                            rewards are tied
                person_id = The person id from meekbot.person for the user
                reward_pts = The current number of reward points
        """
        print('Updating Reward Points')
        sql = """ UPDATE meekbot.person_stream_reward SET qty={}, updt_dt_tm=now() 
                  WHERE stream_id = {} and person_id = {} and active_ind = true; """
    
        try:           
            with self.get_cursor() as cursor:
                cursor.execute(sql.format(reward_pts, stream_id, person_id))
        except:
            print("Failed updating reward points from dbshell.update_user_rewards")
        