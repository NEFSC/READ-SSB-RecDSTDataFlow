/*this do file does two important things.
1. It sets a username into $user. This will be referenced later
2. It sets up globals that hold a folder_setup do file. 
This should be renamed profile.do and placed somewhere that your stata install can find. In my case, this is c:\ado\profile.do
*/
global user minyangWin


global mobility "C:\Users\Min-Yang.Lee\Documents\incomemobility\stata_code\project_logistics\folder_setup_globals.do"
global aceprice "C:\Users\Min-Yang.Lee\Documents\aceprice\stata_code\project_logistics\folder_setup_globals.do"
global RFAdataset "C:\Users\Min-Yang.Lee\Documents\RFAdataset\stata_code\project_logistics\folder_setup_globals.do"

/* if you've used odbc to define newnova and stored your oracle user and pass , this will setup a global that will help you connect to the databases */
global myNEFSC_USERS_conn "dsn(newnova) user($myuid) password(${mypwd}) lower"
