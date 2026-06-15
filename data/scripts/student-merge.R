d1=read.table("../raw/student-mat.csv",sep=";",header=TRUE)
d2=read.table("../raw/student-por.csv",sep=",",header=TRUE)

d3=merge(d1,d2,by=c("school","sex","age","address","famsize","Pstatus","Medu","Fedu","Mjob","Fjob","reason","nursery","internet"))
dir.create("../processed", showWarnings=FALSE)
write.csv(d3, "../processed/student-merged-r.csv", row.names=FALSE)
print(nrow(d3)) # 382 students
