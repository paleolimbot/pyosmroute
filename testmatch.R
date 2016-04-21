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
  linesjson <- lapply(rjson::fromJSON(file=linesfile), data.frame)
  
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
      points(gpspoints, pch=18, cex=0.5)
      segments(segs$p1_lon, segs$p1_lat, segs$p2_lon, segs$p2_lat, col="blue", lwd=2)
      for(l in linesjson) {
        lines(l$lon, l$lat, col="green", lwd=1.5)
      }
      points(out$pt_onseg_lon, out$pt_onseg_lat, col="red", cex=0.1)
    }, title = basename(csvfile))
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

# latest funky matches
matchtrip("example-data/test/allan-huawei_191802.csv") # breaks
matchtrip("example-data/test/allan-samsung_423901.csv")
matchtrip("example-data/test/dr@zensur.io_355953.csv") # out/ back issue remains
matchtrip("example-data/test/dr@zensur.io_463534.csv") # out/ back issue remains
matchtrip("example-data/test/dr@zensur.io_463617.csv")
matchtrip("example-data/test/dr@zensur.io_774319.csv")
matchtrip("example-data/test/dr@zensur.io_959184.csv") # out/ back issue remains

matchtrip("example-data/test/2016-03-02 18_03_07_Car - Normal Drive_Android.csv") # endpoints
matchtrip("example-data/test/trip_3185f564-2259-4351-a6f7-c8b08bd5866e.csv") # out/back, endpoints

# check pypy
matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android_start.csv",
          interpreter = "../../build/pypy-5.0.0-osx64/bin/pypy")

matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv",
          interpreter = "python3")

matchtrip("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android_end.csv",
          interpreter = "python")
