# Get Economic data from FRED
library(fredr)


# Make sure you have an API key and have set it in your .Renviron or .Rprofile 
# If you have done this properly, you the following command should print your API key.

Sys.getenv("FRED_API_KEY")

# Extract some data.
deflators <- fredr(
  series_id = "GDPDEF",
  observation_start = as.Date("2007-01-01"),
  observation_end = as.Date("2022-06-01"),
  realtime_start =NULL,
  realtime_end =NULL,
  frequency = "q")
