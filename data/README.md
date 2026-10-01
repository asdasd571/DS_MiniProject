# 데이터 준비

원본 MIT-Stanford Battery Dataset MAT 파일은 용량 때문에 Git에 포함하지 않습니다.
다음 세 파일을 이 디렉터리에 복사하거나 `python -m src.train` 실행 시 절대 경로로 지정합니다.

- `2017-05-12_batchdata_updated_struct_errorcorrect.mat` (Batch 1, 학습)
- `2018-02-20_batchdata_updated_struct_errorcorrect.mat` (Batch 2, 최종 테스트)
- `2018-04-12_batchdata_updated_struct_errorcorrect.mat` (Batch 3, 추가 일반화 테스트)

`2018-04-03_varcharge_batchdata_updated_struct_errorcorrect.mat`은 기본 분석에서 사용하지 않습니다.
