# File attachments for each command
file_attachments = [
    {
        "data/repl1_Specimen_002_A1_A01.fcs": "Full_Circuit, doxycycline 0.0uM (replicate 1)",
        "data/repl2_Specimen_002_A1_A01.fcs": "Full_Circuit, doxycycline 0.0uM (replicate 2)",
        "data/repl3_Specimen_002_A1_A01.fcs": "Full_Circuit, doxycycline 0.0uM (replicate 3)",
        "data/repl1_Specimen_002_A2_A02.fcs": "Full_Circuit, doxycycline 100.0uM (replicate 1)",
        "data/repl2_Specimen_002_A2_A02.fcs": "Full_Circuit, doxycycline 100.0uM (replicate 2)",
        "data/repl3_Specimen_002_A2_A02.fcs": "Full_Circuit, doxycycline 100.0uM (replicate 3)",
        "data/repl1_Specimen_002_A3_A03.fcs": "Full_Circuit, doxycycline 500.0uM (replicate 1)",
        "data/repl2_Specimen_002_A3_A03.fcs": "Full_Circuit, doxycycline 500.0uM (replicate 2)",
        "data/repl3_Specimen_002_A3_A03.fcs": "Full_Circuit, doxycycline 500.0uM (replicate 3)",
        "data/repl1_Specimen_002_A4_A04.fcs": "Full_Circuit, doxycycline 4000.0uM (replicate 1)",
        "data/repl2_Specimen_002_A4_A04.fcs": "Full_Circuit, doxycycline 4000.0uM (replicate 2)",
        "data/repl3_Specimen_002_A4_A04.fcs": "Full_Circuit, doxycycline 4000.0uM (replicate 3)",
        "data/repl1_Specimen_002_C5_C05.fcs": "No_gRNA, doxycycline 0.0uM (replicate 1)",
        "data/repl2_Specimen_002_C5_C05.fcs": "No_gRNA, doxycycline 0.0uM (replicate 2)",
        "data/repl3_Specimen_002_C5_C05.fcs": "No_gRNA, doxycycline 0.0uM (replicate 3)",
        "data/repl1_Specimen_002_C6_C06.fcs": "No_gRNA, doxycycline 100.0uM (replicate 1)",
        "data/repl2_Specimen_002_C6_C06.fcs": "No_gRNA, doxycycline 100.0uM (replicate 2)",
        "data/repl3_Specimen_002_C6_C06.fcs": "No_gRNA, doxycycline 100.0uM (replicate 3)",
        "data/repl1_Specimen_002_C7_C07.fcs": "No_gRNA, doxycycline 500.0uM (replicate 1)",
        "data/repl2_Specimen_002_C7_C07.fcs": "No_gRNA, doxycycline 500.0uM (replicate 2)",
        "data/repl3_Specimen_002_C7_C07.fcs": "No_gRNA, doxycycline 500.0uM (replicate 3)",
        "data/repl1_Specimen_002_C8_C08.fcs": "No_gRNA, doxycycline 4000.0uM (replicate 1)",
        "data/repl2_Specimen_002_C8_C08.fcs": "No_gRNA, doxycycline 4000.0uM (replicate 2)",
        "data/repl3_Specimen_002_C8_C08.fcs": "No_gRNA, doxycycline 4000.0uM (replicate 3)",
        "data/repl1_Specimen_002_D1_D01.fcs": "No_Cas9, doxycycline 0.0uM (replicate 1)",
        "data/repl2_Specimen_002_D1_D01.fcs": "No_Cas9, doxycycline 0.0uM (replicate 2)",
        "data/repl3_Specimen_002_D1_D01.fcs": "No_Cas9, doxycycline 0.0uM (replicate 3)",
        "data/repl1_Specimen_002_D2_D02.fcs": "No_Cas9, doxycycline 100.0uM (replicate 1)",
        "data/repl2_Specimen_002_D2_D02.fcs": "No_Cas9, doxycycline 100.0uM (replicate 2)",
        "data/repl3_Specimen_002_D2_D02.fcs": "No_Cas9, doxycycline 100.0uM (replicate 3)",
        "data/repl1_Specimen_002_D3_D03.fcs": "No_Cas9, doxycycline 500.0uM (replicate 1)",
        "data/repl2_Specimen_002_D3_D03.fcs": "No_Cas9, doxycycline 500.0uM (replicate 2)",
        "data/repl3_Specimen_002_D3_D03.fcs": "No_Cas9, doxycycline 500.0uM (replicate 3)",
        "data/repl1_Specimen_002_D4_D04.fcs": "No_Cas9, doxycycline 4000.0uM (replicate 1)",
        "data/repl2_Specimen_002_D4_D04.fcs": "No_Cas9, doxycycline 4000.0uM (replicate 2)",
        "data/repl3_Specimen_002_D4_D04.fcs": "No_Cas9, doxycycline 4000.0uM (replicate 3)",
    }
]

commands = ["""
            첨부된 데이터는 Doxycycline의 용량 의존성을 확인하기 위한 Flow cytometry 데이터야. 이 데이터에 대해서 다음의 전처리 및 분석을 수행하고, 각 단계마다 적절한 시각화도 추가해줘.
            1. 적절한 Gating 전략 수립 및 적용
            2. 살아있는 단일 세포 선택: FSC-A vs SSC-A로 온전한 세포 선택 등
            3. 형질주입 마커(mKate) 기반 양성 세포 선택: 명확한 임계값 설정(예: >106 MEFL), 비형질주입 대조군과 비교하여 임계값 검증 등
            4. 데이터 세분화 및 통계 분석: 로그 스케일에서 10 bins/decade로 데이터 세분화, 각 bin에서 EYFP의 기하평균 및 분산 계산, 이상치 제거(최소 100개 데이터 포인트가 없는 bins 제외), (선택사항) 복잡한 분포의 경우 mixture-of-gaussians 고려 등
            5. 실험 조건 간 비교 및 용량-반응 분석: Full_Circuit/No_Cas9/No_gRNA 그룹 간 EYFP 발현 비교, 용량-반응 곡선, 통계적 유의성 검정 등
"""]

"""
            이 때, 다음의 전처리 및 분석 방법들을 참조해.
            - 데이터 전처리: 이상치 및 debris 제거, Doublet 필터링, 채널 간 보상, 배치 효과 보정, 데이터 정규화 및 스케일링 등
            - Quality control: 시간에 따른 신호 안정성 평가, 채널별 신호 대 잡음비 분석, 샘플 간 변동성 평가, 형광 보상 정확도 검증, 마커 발현 범위 확인 등
            - 수동 게이팅 분석: 계층적 게이팅 전략 설계, 살아있는 세포 선별, 특정 세포 유형 마커 기반 게이팅 등
            - 자동 Clustering: 비지도 학습 알고리즘 적용, 최적 Cluster 수 결정, Cluster 간 마커 발현 차이 분석, Cluster 시각화, Cluster 결과와 수동 게이팅 비교 등
            - 세포 유형 주석 및 분류 : 마커 발현 패턴 기반 Cell type annotation, 통계 검정 등
            - Trajectory analysis: 세포 분화/전환 경로 추론, pseudotime 계산, 연속적 세포 상태 변화 모델링, 분기점 식별 등
"""