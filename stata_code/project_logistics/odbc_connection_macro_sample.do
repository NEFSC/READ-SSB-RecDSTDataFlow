/* setup global macros for connecting to oracle sole or nova under windows and linux */
/* Because there may be semicolons inside the connection string, you should use carriage returns as delimiters in this file*/
/* Usage: Either 
1. copy/paste parts of this into your profile.do file OR
2. Run this file right before you need to extract data.
*/

/********************************************************************************************************/
/* PART 0: Preamble */
version 15.1
#delimit cr
global myuid "your_uid"
global mypwd "your_pwd_here"
global mygarfo_pwd "your_garfo_pwd"
/********************************************************************************************************/
/********************************************************************************************************/


/********************************************************************************************************/
/********************************************************************************************************/
/* PART 1: WINDOWS */
/* if DMS has properly configured your ODBC connection using ODBC Driver Manager, this will work on Windows. */
/* The following code assumes that you have a User DSN called "db1name" set up that connects to a database */
/* that database should probably be set up using an ODBC driver from instantclient and the tsnnames.ora file */
/* Min-Yang's preferred approach to connecting to NEFSC's Oracle from Stata in Windows is:


odbc load,  exec("select something from schema.table 
	where blah blah blah;")
	conn("$mydb1_connection") lower;

where $mydb1_connection contains a connection string for sole */

global mydb1_connection "dsn(db1name) user($myuid) password($mypwd) lower"
global mygarfo_conn "dsn(garfo_name) user($myuid) password($mygarfo_pwd) lower"
/********************************************************************************************************/
/********************************************************************************************************/




/********************************************************************************************************/
/********************************************************************************************************/
/********************************************************************************************************/


/*code to test
odbc load, exec("select * from cfdbs.cfspp") $mydb1_connection
*/


*/
