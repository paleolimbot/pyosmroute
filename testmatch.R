library(prettymapr)
library(rosm)
library(sp)

matchtrip <- function(csvfile, printoutput=FALSE) {
  
  if(printoutput) {
    output <- system(paste("python3 matchcsv.py",
      shQuote(csvfile), "--verbose --writesegs --writepoints", "2>&1"), intern = TRUE)
    cat("```\n")
    print(output)
    cat("\n```")
    cat("\n\n")
  } else {
    system(paste("python3 matchcsv.py",
                 shQuote(csvfile), "--verbose --writesegs --writepoints"))
  }
  
  # read CSV output
  outfile <- paste0(substr(csvfile, 1, nchar(csvfile)-4), "_osmsegs.csv")
  pointsfile <- paste0(substr(csvfile, 1, nchar(csvfile)-4), "_osmpoints.csv")
  
  if(!file.exists(outfile)) {
    return(FALSE)
  }
  segs <- read.csv(outfile)
  out <- read.csv(pointsfile)
  
  unlink(outfile)
  unlink(pointsfile)
  
  gps <- read.csv(csvfile, skip=1)
  gpspoints <- coordinates(cbind(out$gps_Longitude, out$gps_Latitude))
  #gpspoints <- coordinates(cbind(gps$Longitude, gps$Latitude))
  
  suppressWarnings(suppressMessages(
    prettymap({
      osm.plot(zoombbox(bbox(gpspoints), 0.9), project=F, stoponlargerequest = F)
      points(gpspoints, pch=18, cex=0.5)
      segments(segs$p1_lon, segs$p1_lat, segs$p2_lon, segs$p2_lat, col="blue", lwd=2)
      points(out$pt_onseg_lon, out$pt_onseg_lat, col="red", cex=0.3)
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