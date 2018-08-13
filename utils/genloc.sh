#!/bin/bash

# generates location file with two accounts of 50000 locations each.
main()
{
    exec 3> location.csv    
    echo "AccountNumber,LocationNumber,LocPeril,DedCode1,DedType1,Ded1,MinDed1,MaxDed1,DedCode2,DedType2,Ded2,MinDed2,MaxDed2,DedCode3,DedType3,Ded3,MinDed3,MaxDed3,DedCode4,DedType4,Ded4,MinDed4,MaxDed4,DedCode5,DedType5,Ded5,MinDed5,MaxDed5,DedCode6,DedType6,Ded6,MinDed6,MaxDed6,LimitCode1,LimitType1,Limit1,LimitCode2,LimitType2,Limit2,LimitCode3,LimitType3,Limit3,LimitCode4,LimitType4,Limit4,LimitCode5,LimitType5,Limit5,LimitCode6,LimitType6,Limit6,BIWaitingPeriod,CountryISO,AreaCode,SubArea,BuildingTIV,OtherTIV,ContentsTIV,BITIV,ConditionTag" >&3
	for i in {1..50000};
    do 
    	echo "1,$i,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,100,0,US,CA,,1000 ,0 ,500 ,500 ,"  >&3 
	done
	for i in {50001..100000};
	do
		echo "2,$i,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,100,0,US,CA,,1000 ,0 ,500 ,500 ,"  >&3 
    done
}

main