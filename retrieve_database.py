import SPIStaffOutlineSystem
import mysql.connector


class Database_Operatjion(SPIStaffOutlineSystem):
    def __init__(self):
        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="your code",
            database="database_name"
        )
        self.cursor = self.connection.cursor()


class Create_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        

    def create_new_course(self,  course_name: str,  course_code: str):
        pass


class Read_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        pass


    def get_user_role(self, email: str) ->str :
        """
        Retrieve a user's role from the database using their email address.

        Args:
        email (str): The email address of the user.

        Returns:
        str | None: The user's role if found, otherwise None.
        """
        try:
            sql = """
                SELECT ???
                FROM ???
                WHERE email = %s
            """

            self.cursor.execute(sql, (email,))
            result = self.cursor.fetchone()

            # No user is found, more error type will be update in the future
            if not result:
                return None
            

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result[0]

    
    def get_user_all_course(self, email: str) ->  list:
        """
        Retrieve all the courses which are relevant to the user

        Args:
        email(str): The email address of that user

        Returns:
        list | None: The all relevant course codes(str)
        """
        try:
            sql= """
                SELECT ???
                FROM ???
                WHERE email = %s
            """
            self.cursor.execute(sql, (email,))
            result = self.cursor.fetchall()

            # If nothing is found in database, more error type will be update in the future
            if not result:
                return None

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result


    def get_course_info(self, coursecode: str,  version: float) ->  str:
        """
        Retrieve the current version of that course

        Args:
        coursecode(str): The course code of taht course         [eg: BCOMP112]

        Returns:
        str | None: The current version of that course       [eg:  "2.12"]
        """
        try:
            sql= """
                SELECT ???, ???
                FROM ???
                WHERE coursecode = %s, version = %s;
            """
            self.cursor.execute(sql, (coursecode, version))
            result = self.cursor.fetchone()

            # If nothing is found in database, more error type will be update in the future
            if not result:
                return None

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result


    def get_course_start_trimester(self, coursecode: str) ->  list:
        """
        Retrieve the starting trimester of that course

        Args:
        coursecode(str): The course code of taht course         [eg: BCOMP112]

        Returns:
        list(str) | None: The semester of a specific year       [eg:  ["2", "2026"]]
        """
        try:
            sql= """
                SELECT ???, ???
                FROM ???
                WHERE coursecode = %s;
            """
            self.cursor.execute(sql, (coursecode,))
            result = self.cursor.fetchall()

            # If nothing is found in database, more error type will be update in the future
            if not result:
                return None

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result


    def get_current_course_version(self, coursecode: str) ->  float:
        """
        Retrieve the current version of that course

        Args:
        coursecode(str): The course code of taht course         [eg: BCOMP112]

        Returns:
        float | None: The current version of that course       [eg:  2.12]
        """
        try:
            sql= """
                SELECT ???, ???
                FROM ???
                WHERE coursecode = %s;
            """
            self.cursor.execute(sql, (coursecode,))
            result = self.cursor.fetchone()

            # If nothing is found in database, more error type will be update in the future
            if not result:
                return None

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result


    def get_current_course_history_log(self, coursecode: str) ->  list:
        """
        Retrieve all versions of that course

        Args:
        coursecode(str): The course code of taht course         [eg: BCOMP112]

        Returns:
        list(float) | None: All versions of that course       [eg:  [2.0, 1.3, 1.2, 1.1, 1.0]]
        """
        try:
            sql= """
                SELECT ???, ???
                FROM ???
                WHERE coursecode = %s;
            """
            self.cursor.execute(sql, (coursecode,))
            result = self.cursor.fetchone()

            # If nothing is found in database, more error type will be update in the future
            if not result:
                return None

        except mysql.connector.Error as error:
            print(f"Database error: {error}")
            return None

        else:
            return result



class Update_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        






class Delete_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        

