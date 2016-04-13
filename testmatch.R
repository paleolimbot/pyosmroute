library(prettymapr)
library(rosm)
library(sp)

matchtrip <- function(csvfile, printoutput=FALSE, interpreter="python") {
  
  if(printoutput) {
    output <- system(paste(interpreter, "matchcsv.py",
      shQuote(csvfile), "--verbose --writesegs --writepoints", "2>&1"), intern = TRUE)
    cat("```\n")
    print(output)
    cat("\n```")
    cat("\n\n")
  } else {
    system(paste(interpreter, "matchcsv.py",
                 shQuote(csvfile), "--verbose --writesegs --writepoints --writelines"))
  }
  
  # read CSV output
  outfile <- paste0(substr(csvfile, 1, nchar(csvfile)-4), "_osmsegs.csv")
  pointsfile <- paste0(substr(csvfile, 1, nchar(csvfile)-4), "_osmpoints.csv")
  linesfile <- paste0(substr(csvfile, 1, nchar(csvfile)-4), "_osmlines.json")
  
  if(!file.exists(outfile)) {
    return(FALSE)
  }
  segs <- read.csv(outfile)
  out <- read.csv(pointsfile)
  linesjson <- data.frame(rjson::fromJSON(file=linesfile))
  
  unlink(outfile)
  unlink(pointsfile)
  unlink(linesfile)
  
  gps <- read.csv(csvfile, skip=1)
  if(is.null(cbind(out$gps_Longitude, out$gps_Latitude))) {
    browser()
  }
  gpspoints <- coordinates(cbind(out$gps_Longitude, out$gps_Latitude))
  #gpspoints <- coordinates(cbind(gps$Longitude, gps$Latitude))
  
  suppressWarnings(suppressMessages(
    prettymap({
      osm.plot(zoombbox(bbox(gpspoints), 0.9), project=F, stoponlargerequest = F)
      points(gpspoints, pch=18, cex=0.1)
      segments(segs$p1_lon, segs$p1_lat, segs$p2_lon, segs$p2_lat, col="blue", lwd=2)
      lines(linesjson$lon, linesjson$lat, col="green", lwd=1.5)
      points(out$pt_onseg_lon, out$pt_onseg_lat, col="red", cex=0.1)
    })
  ))
  
  if(printoutput) {
    cat("\n\n")
  }
  
  return(TRUE)
}


test <- function() {
  folder <- "example-data/test"
  trips <- list.files(folder, pattern="*.csv", full.names = TRUE)
  
  for(trip in trips) {
    matchtrip(trip)
    # browser()
  }
}

matchtrip("example-data/test/christest_3.csv")

# check pypy
matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android_start.csv",
          interpreter = "../../build/pypy-5.0.0-osx64/bin/pypy")

matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv",
          interpreter = "python3")

matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android_end.csv",
          interpreter = "python")
