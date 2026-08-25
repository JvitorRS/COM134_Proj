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
        list | None: The all relevant courses(str)
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
                WHERE coursecode = %s
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





        

class Update_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        pass

class Delete_Database(Database_Operatjion):
    def __init__(self):
        super().__init__()
        pass

