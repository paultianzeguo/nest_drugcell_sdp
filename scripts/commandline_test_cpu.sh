#!/bin/bash
homedir=$1
gene2idfile="${homedir}/data/gene2ind.txt"
cell2idfile="${homedir}/data/cell2ind.txt"
drug2idfile="${homedir}/data/drug2ind.txt"
mutationfile="${homedir}/data/cell2mutation.txt"
drugfile="${homedir}/data/drug2fingerprint.txt"
testdatafile="${homedir}/data/drugcell_all.txt"

modelfile="${homedir}/models/model_final.pt"
resultdir="${homedir}/result"
mkdir -p $resultdir

hiddendir="${homedir}/hidden"
if [ -d $hiddendir ]
then
	rm -rf $hiddendir
	mkdir $hiddendir
fi

pyScript="${homedir}/code/predict_drugcell_cpu.py"

source activate pytorch3drugcellcpu

python -u $pyScript -gene2id $gene2idfile -cell2id $cell2idfile -drug2id $drug2idfile \
	-genotype $mutationfile -fingerprint $drugfile -hidden $hiddendir -result $resultdir \
	-predict $testdatafile -load $modelfile > test.log
