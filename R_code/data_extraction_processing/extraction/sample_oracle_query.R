# This is code that uses ROracle to connect to oracle databases. 
# This assumes you have adapted  .Rprofile_sample and it is executed on startup

library("ROracle")
# library("keyring") already loaded by .Rprofile on startup


drv<-dbDriver("Oracle")

oracle_connected<-eval(nefscdb_con)

querystring<-paste0("select gearcode, negear, negear2, gearnm from vtr.vlgear")
VTRgear<-dbGetQuery(oracle_connected, querystring)


dbDisconnect(oracle_connected)

