## Regenerate CITATION.cff from an R package DESCRIPTION file.
##
## Required environment variables:
## - DESCRIPTION_FILE: path to the package DESCRIPTION file
## - CITATION_FILE: path to the CITATION.cff file to overwrite
##
## If the existing citation file already has an `identifiers` field, preserve it
## after cffr rewrites the rest of the citation metadata from DESCRIPTION.

if (!requireNamespace("cffr", quietly = TRUE)) {
  stop(
    "Missing required R package: cffr. ",
    "Install it in workflow setup (e.g. setup-r-dependencies)."
  )
}

citation_file <- Sys.getenv("CITATION_FILE")
existing_identifiers <- NULL
if (file.exists(citation_file)) {
  tryCatch(
    {
      existing_cff <- cffr::cff_read(citation_file)
      if (!is.null(existing_cff[["identifiers"]])) {
        existing_identifiers <- existing_cff[["identifiers"]]
      }
    },
    error = function(e) {
      warning(
        "Unable to preserve existing CITATION.cff identifiers: ",
        conditionMessage(e)
      )
      NULL
    }
  )
}

setwd(dirname(Sys.getenv("DESCRIPTION_FILE")))

# Create citation with custom identifiers if they exist
custom_keys <- if (is.null(existing_identifiers)) {
  list()
} else {
  list(identifiers = existing_identifiers)
}
cf <- cffr::cff_create(keys = custom_keys)
cffr::cff_write(cf, outfile = citation_file)
