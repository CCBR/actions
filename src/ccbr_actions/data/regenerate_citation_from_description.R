for (pkg in c("cffr", "yaml")) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop(
      "Missing required R package: ",
      pkg,
      ". Install it in workflow setup (e.g. setup-r-dependencies)."
    )
  }
}

citation_file <- Sys.getenv("CITATION_FILE")
custom_identifiers <- NULL
if (file.exists(citation_file)) {
  tryCatch(
    {
      existing_cff <- cffr::cff_read(citation_file)
      if (!is.null(existing_cff[["identifiers"]])) {
        custom_identifiers <- existing_cff[["identifiers"]]
      }
    },
    error = function(e) {
      NULL
    }
  )
}

setwd(dirname(Sys.getenv("DESCRIPTION_FILE")))
cffr::cff_write(outfile = citation_file)
if (!is.null(custom_identifiers)) {
  yml <- yaml::read_yaml(citation_file)
  yml$identifiers <- custom_identifiers
  yaml::write_yaml(yml, citation_file)
}
