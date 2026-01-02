# 라이브러리 라이센스 분석 보고서
## 배포 시나리오별 상업적 이용 분석

---

## 📊 요약 비교

### SaaS (클라우드 서비스) 배포 시

| 구분 | 개수 | 비율 |
|------|------|------|
| ✅ 이용 가능 | 112 | 98.2% |
| ⚠️ 조건부 이용 | 0 | 0.0% |
| ❌ 소스 공개 필요 | 0 | 0.0% |
| ❓ 확인 필요 | 2 | 1.8% |
| **총계** | **114** | **100%** |

### On-premise (고객사 설치) 배포 시

| 구분 | 개수 | 비율 |
|------|------|------|
| ✅ 이용 가능 | 85 | 74.6% |
| ⚠️ 조건부 이용 | 27 | 23.7% |
| ❌ 소스 공개 필요 | 0 | 0.0% |
| ❓ 확인 필요 | 2 | 1.8% |
| **총계** | **114** | **100%** |

---

## 📚 라이센스 유형별 설명

### SaaS vs On-premise 차이점

| 라이센스 유형 | SaaS 배포 | On-premise 배포 | 이유 |
|--------------|-----------|-----------------|------|
| **MIT, BSD, Apache** | ✅ 이용 가능 | ✅ 이용 가능 | 허용적 라이센스, 저작권 표기만 필요 |
| **LGPL** | ✅ 이용 가능 | ⚠️ 조건부 | 동적 링크 시 본인 코드 비공개 가능 (Python은 대부분 해당) |
| **GPL** | ✅ 이용 가능* | ⚠️ 소스 공개 필요 | SaaS는 배포가 아님 (SaaS Loophole), On-premise는 배포에 해당 |
| **AGPL** | ❌ 소스 공개 필요 | ⚠️ 소스 공개 필요 | 네트워크 서비스도 배포로 간주 |

> *SaaS Loophole: GPL은 "배포" 시에만 소스 공개 의무가 발생. 서버에서 실행하고 네트워크로 서비스만 제공하는 SaaS는 법적으로 "배포"가 아니므로 소스 공개 의무 없음.

---

## 🔧 Conda 패키지 목록

| 패키지 | 라이센스 | SaaS | On-premise | 버전 |
|--------|----------|------|------------|------|
| anndata | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.12.7 |
| beautifulsoup4 | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 4.14.3 |
| bedtools | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2.31.1 |
| bioconductor-clusterprofiler | Artistic-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 4.14.0 |
| bioconductor-deseq2 | LGPL (>= 3) | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 1.46.0 |
| bioconductor-edger | GPL (>=2) | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 4.4.0 |
| bioconductor-genomeinfodb | Artistic-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 1.42.0 |
| bioconductor-geoquery | MIT + file LICENSE | ✅ 이용 가능 | ✅ 이용 가능 | 2.74.0 |
| bioconductor-hgu133plus2.db | Artistic-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 3.13.0 |
| bioconductor-limma | GPL (>=2) | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 3.62.1 |
| bioconductor-org.hs.eg.db | Artistic-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 3.20.0 |
| biopandas | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.5.1 |
| biopython | LicenseRef-Biopython | ✅ 이용 가능 | ✅ 이용 가능 | 1.86 |
| blast | NCBI-PD | ✅ 이용 가능 | ✅ 이용 가능 | 2.17.0 |
| bowtie2 | GPL-3.0-only | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 2.5.4 |
| bwa | GPL3 | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.7.19 |
| cellxgene-census | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.17.0 |
| chainlit | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 2.9.4 |
| cooler | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.10.4 |
| cython | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 3.2.3 |
| docstring_parser | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.17.0 |
| faiss-cpu | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.9.0 |
| fastqc | GPL >=3 | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.12.1 |
| gget | Apache-2.0 AND GPL-3.0-only AND BSD... | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.29.3 |
| gradio | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 6.2.0 |
| gseapy | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.1.11 |
| harmony-pytorch | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.1.8 |
| hdbscan | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.8.41 |
| hmmlearn | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.3.3 |
| igraph | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.0.1 |
| ipykernel | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 7.1.0 |
| jupyter | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.1.1 |
| leidenalg | GPL-3.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.11.0 |
| lifelines | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.30.0 |
| louvain | GPL-3.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.8.2 |
| lxml | BSD-3-Clause and MIT-CMU | ✅ 이용 가능 | ✅ 이용 가능 | 6.0.2 |
| macs3 | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 3.0.3 |
| mafft | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 7.526 |
| mageck | BSD License | ✅ 이용 가능 | ✅ 이용 가능 | 0.5.9.5 |
| markdown | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 3.10 |
| matplotlib | PSF-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 3.10.8 |
| msprime | GPL-3.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.3.4 |
| networkx | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 3.6.1 |
| notebook | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 7.5.1 |
| numpy | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 2.4.0 |
| openai | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2.14.0 |
| openpyxl | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 3.1.5 |
| pandas | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 2.3.3 |
| pip | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 25.3 |
| pybedtools | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.12.0 |
| pyfaidx | BSD | ✅ 이용 가능 | ✅ 이용 가능 | 0.9.0.3 |
| pyliftover | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.4.1 |
| pyranges | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.1.4 |
| pysam | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.23.3 |
| pytest | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 9.0.2 |
| python | Python-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 3.14.2 |
| python-dotenv | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.2.1 |
| pytz | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2025.2 |
| pyyaml | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 6.0.3 |
| r-base | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 4.5.2 |
| r-dplyr | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.1.4 |
| r-ggplot2 | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 4.0.1 |
| r-glmnet | GPL-2.0-only | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 4.1_8 |
| r-harmony | GPL-3.0-only | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.2.4 |
| r-lme4 | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.1_34 |
| r-matrix | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.7_2 |
| r-rcpp | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 1.1.0 |
| r-readr | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2.1.6 |
| r-remotes | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 2.5.0 |
| r-stringr | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.6.0 |
| r-survival | LGPL-2.0-or-later | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 3.2_13 |
| r-survminer | GPL-2.0-only | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.5.1 |
| r-tidyr | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.3.2 |
| rdkit | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | Release_2017_09_3 |
| requests | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 2.32.5 |
| samtools | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.23 |
| scanpy | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.11.5 |
| scikit-bio | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.7.1 |
| scikit-learn | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.8.0 |
| scipy | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.16.3 |
| scrublet | MIT License | ✅ 이용 가능 | ✅ 이용 가능 | 0.2.3 |
| scvelo | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.3.3 |
| scvi-tools | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 1.4.1 |
| seaborn | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.13.2 |
| sentencepiece | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 0.2.1 |
| statsmodels | BSD-3-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.14.6 |
| tqdm | MPL-2.0 or MIT | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 4.67.1 |
| transformers | Apache-2.0 | ✅ 이용 가능 | ✅ 이용 가능 | 4.57.3 |
| trimmomatic | GPL-3.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.40 |
| tskit | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.0.0 |
| umap-learn | BSD-2-Clause | ✅ 이용 가능 | ✅ 이용 가능 | 0.5.9.post2 |
| viennarna | custom | ❓ 확인 필요 | ❓ 확인 필요 | 2.7.1 |
| xz | 0BSD AND LGPL-2.1-or-later AND GPL-... | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 5.8.1 |

---

## 📦 PyPI 패키지 목록

| 패키지 | 라이센스 | SaaS | On-premise | 버전 |
|--------|----------|------|------------|------|
| aiosqlite | MIT License | ✅ 이용 가능 | ✅ 이용 가능 | 0.22.1 |
| cobra | LGPL-2.0-or-later OR GPL-2.0-or-lat... | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 0.30.0 |
| ddgs | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 9.10.0 |
| e2b | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2.9.0 |
| e2b-code-interpreter | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 2.4.1 |
| googlesearch-python | MIT License | ✅ 이용 가능 | ✅ 이용 가능 | 1.3.0 |
| langchain | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.2.0 |
| langchain-aws | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.2.0 |
| langchain-community | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.4.1 |
| langchain-google-genai | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 4.1.2 |
| langchain-openai | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.1.6 |
| langchain-qdrant | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.1.0 |
| langgraph | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.0.5 |
| mcp | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 1.25.0 |
| mygene | BSD | ✅ 이용 가능 | ✅ 이용 가능 | 3.2.2 |
| pylint | GPL-2.0-or-later | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 4.0.4 |
| pymed | MIT | ✅ 이용 가능 | ✅ 이용 가능 | 0.8.9 |
| pypdf2 | BSD License | ✅ 이용 가능 | ✅ 이용 가능 | 3.0.1 |
| pyscenic | GPL-3.0+ | ✅ 이용 가능 (SaaS Loophole) | ⚠️ 소스 공개 필요 | 0.12.1 |
| python-libsbml | LGPL | ✅ 이용 가능 | ⚠️ 조건부 (동적 링크) | 5.20.5 |
| tooluniverse | Unknown | ❓ 확인 필요 | ❓ 확인 필요 | 1.0.14.2 |

---

## ✅ SaaS 배포 시 주의가 필요한 패키지

**AGPL 라이센스 패키지가 없습니다!** SaaS로 서비스 제공 시 소스 공개 없이 이용 가능합니다.

---

## ⚠️ On-premise 배포 시 주의가 필요한 패키지

아래 패키지들은 On-premise로 배포 시 **조건부 이용 또는 소스 공개가 필요**합니다:

| 패키지 | 라이센스 | 상태 | 권장 조치 |
|--------|----------|------|-----------|
| tqdm | MPL-2.0 or MIT | ⚠️ 조건부 (동적 링크) | 법률 자문 권장 |
| bwa | GPL3 | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| bowtie2 | GPL-3.0-only | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| trimmomatic | GPL-3.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| fastqc | GPL >=3 | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| gget | Apache-2.0 AND GPL-3.0-only AND BSD-2-Clause | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| louvain | GPL-3.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| msprime | GPL-3.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| igraph | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| leidenalg | GPL-3.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-lme4 | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| xz | 0BSD AND LGPL-2.1-or-later AND GPL-2.0-or-later | ⚠️ 조건부 (동적 링크) | 동적 링크 사용 (Python은 대부분 해당) |
| r-harmony | GPL-3.0-only | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-remotes | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-matrix | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-rcpp | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-survminer | GPL-2.0-only | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| bioconductor-limma | GPL (>=2) | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| bioconductor-edger | GPL (>=2) | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| bioconductor-deseq2 | LGPL (>= 3) | ⚠️ 조건부 (동적 링크) | 동적 링크 사용 (Python은 대부분 해당) |
| r-survival | LGPL-2.0-or-later | ⚠️ 조건부 (동적 링크) | 동적 링크 사용 (Python은 대부분 해당) |
| r-base | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| r-glmnet | GPL-2.0-only | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| python-libsbml | LGPL | ⚠️ 조건부 (동적 링크) | 동적 링크 사용 (Python은 대부분 해당) |
| pylint | GPL-2.0-or-later | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| pyscenic | GPL-3.0+ | ⚠️ 소스 공개 필요 | 소스 공개 또는 별도 프로세스 실행 |
| cobra | LGPL-2.0-or-later OR GPL-2.0-or-later | ⚠️ 조건부 (동적 링크) | 동적 링크 사용 (Python은 대부분 해당) |

---

## ❓ 추가 확인이 필요한 패키지

아래 패키지들은 라이센스 정보를 자동으로 확인하지 못했습니다. 수동 확인이 필요합니다:

| 패키지 | 조회 결과 | 비고 |
|--------|----------|------|
| viennarna | custom | 라이센스 정보 없음 |
| tooluniverse | Unknown | 라이센스 정보 없음 |

---

## 📋 결론 및 권장사항

### SaaS 배포의 경우
- GPL 라이센스 패키지도 "SaaS Loophole"으로 인해 소스 공개 없이 사용 가능
- **AGPL 패키지만 주의 필요** (현재 목록에 AGPL 패키지가 있다면 위 표 참고)
- 대부분의 패키지가 상업적 이용 가능

### On-premise 배포의 경우
- GPL/LGPL 패키지는 배포에 해당하므로 라이센스 조건 준수 필요
- **LGPL**: Python의 import는 동적 링크로 간주되어 대부분 문제 없음
- **GPL**: 소스 코드 공개 필요. 별도 프로세스로 실행하면 회피 가능한 경우도 있음

### 공통 권장사항
1. 이 보고서는 자동 생성되었으며, **법적 조언이 아닙니다**
2. 중요한 결정을 내리기 전에 **법률 전문가와 상담**하세요
3. 라이센스는 패키지 버전에 따라 변경될 수 있습니다
4. **간접 의존성(transitive dependencies)**도 확인이 필요할 수 있습니다

---

*보고서 생성 도구: check_licenses.py*
