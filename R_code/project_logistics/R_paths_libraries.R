# here is incredibly useful to avoid hardcoded paths.

#Install packages if necessary
if(!require(here)) {  
  install.packages("here")
  require(here)}

# Setup directories
here::i_am("R_code/project_logistics/R_paths_libraries.R")
my_projdir<-here()

#You can use dirname on here() to go "up" one folder.
# my_neighbor_folder<-dirname(here())
#Now you have gone up one folder, you can write the path to another folder 
# my_neighbor_folder<-file.path(my_neighbor_folder,"Neighbor_Folder_to_Find")



# Find the stata executable if you want to run stata from within R

# https://github.com/Hemken/Statamarkdown/blob/master/R/find_stata.r
# Search through places that stata is usually installed.
# Searches largest to smallest, from 18 down.  smallest to highest, which means if you have StataIC and stataMP-64, it will stop at StataIC
# and not pick up StataMP-64 



stataexe <- ""

for (d in c("C:/Program Files","C:/Program Files (x86)")) {
  if (stataexe=="" & dir.exists(d)) {
    for (v in seq(18,11,-1)) {
      dv <- paste(d,paste0("Stata",v), sep="/")
      if (dir.exists(dv)) {
        for (f in c("StataMP-64", "StataSE-64", "StataIC-64", "Stata-64",
                    "StataMP", "StataSE", "StataIC", "Stata")) {
          dvf <- paste(paste(dv, f, sep="/"), "exe", sep=".")
          if (file.exists(dvf)) {
            stataexe <- dvf
          }
          if (stataexe != "") break
        }
      }
      if (stataexe != "") break
    }
  }
  if (stataexe != "") break
}
