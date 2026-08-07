/* Set up global macros to point to folders */

version 15.1

#delimit ;


/*One of these
global user minyangWin; 
global user SomeoneElse; 

*/


/*minyangWin  */
if strmatch("$user","minyangWin"){;
global my_projdir "C:/Users/Min-Yang.Lee/Documents/new-project-templates";
};
if strmatch("$user","SomeoneElse"){;
global my_projdir "C:/Users/Someone.Else/Documents/new-project-templates";
};


/* 

Alternatively, you can use the stata here package

It is not as good as R's version. Before running this code, you must change directories into project directory 
One easy way to do this is to add a line to your profile do that store that directory in the 

global template_dir  "C:/Users/Min-Yang.Lee/Documents/new-project-templates"
cd "$template_dir" right before running this code
and then do 

here, nogit
*/



global my_codedir "${my_projdir}/stata_code";
global extract_process "${my_codedir}/data_extraction_processing";
global extraction_code "${extract_process}/extraction";
global processing_code "${extract_process}/processing";
global analysis_code "${my_codedir}/analysis";
global R_code "${my_projdir}/R_code";
global my_adopath "${my_codedir}/ado";


/* setup data folder */
global my_datadir "${my_projdir}/data_folder";
global data_raw "${my_datadir}/raw";

global data_internal "${my_datadir}/internal";
global data_external"${my_datadir}/external";

global data_main "${my_datadir}/main";

global data_intermediate "${my_datadir}/intermediate";



/* setup results folders */
global intermediate_results "${my_projdir}/intermediate_results";
global my_results "${my_projdir}/results";

/* setup images folders */

global my_images "${my_projdir}/images";
global exploratory "${my_images}/exploratory";

/* setup table folders */
global my_tables "${my_projdir}/tables" ;

/* add the programs in $my_adopath to the adopath*/
adopath + $my_adopath ;


/*set the date field */
local date: display %td_CCYY_NN_DD date(c(current_date), "DMY");
global today_date_string = subinstr(trim("`date'"), " " , "_", .);
global vintage_string $today_date_string;
di "$vintage_string";
vintage_lookup_and_reset;


