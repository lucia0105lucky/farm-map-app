import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="전국 텃밭 정보 지도",
    page_icon="🌱",
    layout="wide"
)

# 커스텀 CSS
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


class FarmDataCollector:
    """텃밭 데이터 수집 클래스"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://211.237.50.150:7080/openapi"
        self.service_name = "Grid_20171122000000000552_1"
        self.all_data = []
    
    def fetch_data(self, start_idx, end_idx):
        """지정된 범위의 데이터 가져오기"""
        url = f"{self.base_url}/{self.api_key}/xml/{self.service_name}/{start_idx}/{end_idx}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # 전체 개수 (태그 직접 찾기)
            total_count_elem = root.find('totalCnt')
            total_count = int(total_count_elem.text) if total_count_elem is not None else 0
            
            # 데이터 추출 (row 태그 직접 찾기)
            data_list = []
            for row in root.findall('row'):
                item = {}
                for child in row:
                    item[child.tag] = child.text if child.text else ""
                data_list.append(item)
            
            return data_list, total_count
            
        except requests.exceptions.RequestException as e:
            st.error(f"API 요청 오류: {e}")
            return [], 0
        except ET.ParseError as e:
            st.error(f"XML 파싱 오류: {e}")
            return [], 0
        except Exception as e:
            st.error(f"데이터 수집 오류: {e}")
            return [], 0
    
    def collect_all_data(self, batch_size=50):
        """전체 데이터 수집"""
        self.all_data = []
        
        # 진행 상황 표시용
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 첫 번째 요청으로 전체 개수 확인
            status_text.text("데이터 수집을 시작합니다...")
            first_data, total_count = self.fetch_data(1, batch_size)
            
            if total_count == 0:
                st.warning("수집할 데이터가 없습니다.")
                return pd.DataFrame()
            
            self.all_data.extend(first_data)
            status_text.text(f"수집 중: {len(self.all_data)}/{total_count}개")
            progress_bar.progress(len(self.all_data) / total_count)
            
            # 나머지 데이터 수집
            current_idx = batch_size + 1
            
            while current_idx <= total_count:
                end_idx = min(current_idx + batch_size - 1, total_count)
                data_list, _ = self.fetch_data(current_idx, end_idx)
                
                if data_list:
                    self.all_data.extend(data_list)
                    status_text.text(f"수집 중: {len(self.all_data)}/{total_count}개")
                    progress_bar.progress(min(len(self.all_data) / total_count, 1.0))
                else:
                    # 실패 시 재시도
                    time.sleep(2)
                    continue
                
                current_idx = end_idx + 1
                time.sleep(0.3)  # API 부하 방지
            
            status_text.text(f"✅ 수집 완료: 총 {len(self.all_data)}개")
            progress_bar.progress(1.0)
            
            # DataFrame 생성
            df = pd.DataFrame(self.all_data)
            
            # CSV로 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"텃밭정보_전체데이터_{timestamp}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            st.success(f"데이터가 '{filename}' 파일로 저장되었습니다.")
            
            return df
            
        except Exception as e:
            st.error(f"데이터 수집 중 오류 발생: {e}")
            return pd.DataFrame()


def create_map(df_filtered):
    """Folium 지도 생성"""
    if df_filtered.empty:
        st.warning("표시할 데이터가 없습니다.")
        return None
    
    # 중심 좌표 계산
    center_lat = df_filtered['POSLAT'].astype(float).mean()
    center_lng = df_filtered['POSLNG'].astype(float).mean()
    
    # 지도 생성
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=8,
        tiles='OpenStreetMap'
    )
    
    # 가격별 색상 함수
    def get_color(price):
        try:
            p = float(price)
            if p <= 20:
                return 'green'
            elif p <= 40:
                return 'orange'
            elif p <= 60:
                return 'red'
            else:
                return 'darkred'
        except:
            return 'gray'
    
    # 마커 추가
    for idx, row in df_filtered.iterrows():
        try:
            lat = float(row['POSLAT'])
            lng = float(row['POSLNG'])
            price = row.get('PRICE', '0')
            
            popup_html = f"""
            <div style="width: 280px; font-family: sans-serif;">
                <h4 style="color: #667eea; margin: 0 0 10px 0;">{row['FARM_NM']}</h4>
                <p style="margin: 5px 0;"><b>📍 주소:</b> {row.get('ADDRESS1', '-')}</p>
                <p style="margin: 5px 0;"><b>💰 가격:</b> {price}만원</p>
                <p style="margin: 5px 0;"><b>📐 면적:</b> {row.get('SELL_AREA_INFO', '-')}㎡</p>
                <p style="margin: 5px 0;"><b>🏢 운영:</b> {row.get('FARM_TYPE', '-')}</p>
                <p style="margin: 5px 0;"><b>📅 모집:</b> {row.get('COLLEC_PROD', '-')}</p>
                <p style="margin: 5px 0;"><b>✅ 신청:</b> {row.get('APPLY_MTHD', '-')}</p>
            </div>
            """
            
            folium.CircleMarker(
                location=[lat, lng],
                radius=8,
                popup=folium.Popup(popup_html, max_width=300),
                color=get_color(price),
                fill=True,
                fillColor=get_color(price),
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        except:
            continue
    
    # 범례 추가
    legend_html = '''
    <div style="position: fixed; 
         bottom: 50px; right: 50px; width: 180px; height: 150px; 
         background-color: white; border:2px solid grey; z-index:9999; 
         font-size:14px; padding: 10px; border-radius: 5px;">
         <p style="margin: 0; font-weight: bold;">분양가격 범위</p>
         <p style="margin: 5px 0;"><span style="color: green;">●</span> 0 ~ 20만원</p>
         <p style="margin: 5px 0;"><span style="color: orange;">●</span> 20 ~ 40만원</p>
         <p style="margin: 5px 0;"><span style="color: red;">●</span> 40 ~ 60만원</p>
         <p style="margin: 5px 0;"><span style="color: darkred;">●</span> 60만원 이상</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m


def main():
    """메인 함수"""
    
    # 타이틀
    st.title("🌱 전국 텃밭 정보 지도")
    st.markdown("---")
    
    # Session State 초기화
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'collected' not in st.session_state:
        st.session_state.collected = False
    
    # API 키 입력
    st.sidebar.header("🔑 API 설정")
    
    # 환경변수에서 API 키 가져오기
    default_key = os.getenv('FARMER_KEY', '')
    
    api_key = st.sidebar.text_input(
        "API 키를 입력하세요",
        value=default_key,
        type="password",
        help="환경변수 FARMER_KEY에 저장된 키를 사용하거나 직접 입력하세요"
    )
    
    # 데이터 수집 버튼
    if st.sidebar.button("📡 데이터 수집 시작", type="primary"):
        if not api_key:
            st.sidebar.error("API 키를 입력해주세요!")
        else:
            with st.spinner("데이터를 수집하고 있습니다..."):
                collector = FarmDataCollector(api_key)
                df = collector.collect_all_data(batch_size=50)
                
                if not df.empty:
                    st.session_state.df = df
                    st.session_state.collected = True
                    st.balloons()
    
    # CSV 파일 업로드 (대안)
    st.sidebar.markdown("---")
    st.sidebar.header("📁 또는 CSV 파일 업로드")
    uploaded_file = st.sidebar.file_uploader(
        "CSV 파일 선택",
        type=['csv']
    )
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.session_state.df = df
            st.session_state.collected = True
            st.sidebar.success(f"✅ 파일 로드 완료: {len(df)}개")
        except Exception as e:
            st.sidebar.error(f"파일 읽기 오류: {e}")
    
    # 데이터가 있으면 시각화
    if st.session_state.collected and st.session_state.df is not None:
        df = st.session_state.df
        
        # 데이터 전처리
        df['PRICE'] = pd.to_numeric(df['PRICE'], errors='coerce').fillna(0)
        df['POSLAT'] = pd.to_numeric(df['POSLAT'], errors='coerce')
        df['POSLNG'] = pd.to_numeric(df['POSLNG'], errors='coerce')
        
        # 유효한 좌표만 필터링
        df_valid = df.dropna(subset=['POSLAT', 'POSLNG'])
        
        # 필터 옵션
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 필터 옵션")
        
        # 지역 필터
        regions = ['전체'] + sorted(df_valid['AREA_LNM'].dropna().unique().tolist())
        selected_region = st.sidebar.selectbox("지역 선택", regions)
        
        # 가격 범위 필터
        min_price = float(df_valid['PRICE'].min())
        max_price = float(df_valid['PRICE'].max())
        
        price_range = st.sidebar.slider(
            "분양가격 범위 (만원)",
            min_value=min_price,
            max_value=max_price,
            value=(min_price, max_price)
        )
        
        # 면적 필터
        if 'SELL_AREA_INFO' in df_valid.columns:
            df_valid['SELL_AREA_INFO'] = pd.to_numeric(df_valid['SELL_AREA_INFO'], errors='coerce').fillna(0)
            min_area = float(df_valid['SELL_AREA_INFO'].min())
            max_area = float(df_valid['SELL_AREA_INFO'].max())
            
            area_range = st.sidebar.slider(
                "분양면적 범위 (㎡)",
                min_value=min_area,
                max_value=max_area,
                value=(min_area, max_area)
            )
        
        # 데이터 필터링
        df_filtered = df_valid.copy()
        
        if selected_region != '전체':
            df_filtered = df_filtered[df_filtered['AREA_LNM'] == selected_region]
        
        df_filtered = df_filtered[
            (df_filtered['PRICE'] >= price_range[0]) & 
            (df_filtered['PRICE'] <= price_range[1])
        ]
        
        if 'SELL_AREA_INFO' in df_valid.columns:
            df_filtered = df_filtered[
                (df_filtered['SELL_AREA_INFO'] >= area_range[0]) & 
                (df_filtered['SELL_AREA_INFO'] <= area_range[1])
            ]
        
        # 통계 정보
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📍 총 텃밭 수", f"{len(df_filtered):,}개")
        
        with col2:
            avg_price = df_filtered['PRICE'].mean()
            st.metric("💰 평균 가격", f"{avg_price:.1f}만원")
        
        with col3:
            region_count = df_filtered['AREA_LNM'].nunique()
            st.metric("🗺️ 지역 수", f"{region_count}개")
        
        with col4:
            min_p = df_filtered['PRICE'].min()
            st.metric("🏷️ 최저 가격", f"{min_p:.0f}만원")
        
        st.markdown("---")
        
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["🗺️ 지도", "📊 통계", "📋 데이터"])
        
        with tab1:
            if not df_filtered.empty:
                m = create_map(df_filtered)
                if m:
                    st_folium(m, width=1400, height=600)
            else:
                st.warning("필터 조건에 맞는 데이터가 없습니다.")
        
        with tab2:
            # 통계 차트
            col1, col2 = st.columns(2)
            
            with col1:
                # 지역별 텃밭 수
                region_counts = df_filtered['AREA_LNM'].value_counts().head(10)
                fig1 = px.bar(
                    x=region_counts.values,
                    y=region_counts.index,
                    orientation='h',
                    title="지역별 텃밭 수 (상위 10개)",
                    labels={'x': '텃밭 수', 'y': '지역'},
                    color=region_counts.values,
                    color_continuous_scale='Viridis'
                )
                fig1.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # 가격 분포
                fig2 = px.histogram(
                    df_filtered,
                    x='PRICE',
                    nbins=30,
                    title="분양가격 분포",
                    labels={'PRICE': '가격 (만원)', 'count': '개수'},
                    color_discrete_sequence=['#667eea']
                )
                fig2.update_layout(height=400)
                st.plotly_chart(fig2, use_container_width=True)
            
            col3, col4 = st.columns(2)
            
            with col3:
                # 지역별 평균 가격
                avg_price_by_region = df_filtered.groupby('AREA_LNM')['PRICE'].mean().sort_values(ascending=False).head(10)
                fig3 = px.bar(
                    x=avg_price_by_region.values,
                    y=avg_price_by_region.index,
                    orientation='h',
                    title="지역별 평균 분양가격 (상위 10개)",
                    labels={'x': '평균 가격 (만원)', 'y': '지역'},
                    color=avg_price_by_region.values,
                    color_continuous_scale='Reds'
                )
                fig3.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig3, use_container_width=True)
            
            with col4:
                # 운영주체별 분포
                if 'FARM_TYPE' in df_filtered.columns:
                    farm_type_counts = df_filtered['FARM_TYPE'].value_counts().head(10)
                    fig4 = px.pie(
                        values=farm_type_counts.values,
                        names=farm_type_counts.index,
                        title="운영주체별 분포 (상위 10개)"
                    )
                    fig4.update_layout(height=400)
                    st.plotly_chart(fig4, use_container_width=True)
        
        with tab3:
            # 데이터 테이블
            st.subheader("📋 필터링된 데이터")
            
            # 컬럼 선택
            display_columns = ['FARM_NM', 'AREA_LNM', 'AREA_MNM', 'ADDRESS1', 
                             'PRICE', 'SELL_AREA_INFO', 'FARM_TYPE', 'APPLY_MTHD']
            display_columns = [col for col in display_columns if col in df_filtered.columns]
            
            st.dataframe(
                df_filtered[display_columns],
                use_container_width=True,
                height=400
            )
            
            # CSV 다운로드
            csv = df_filtered.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 필터링된 데이터 다운로드 (CSV)",
                data=csv,
                file_name=f"필터링된_텃밭정보_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    else:
        # 초기 화면
        st.info("👈 사이드바에서 API 키를 입력하고 데이터 수집을 시작하거나, CSV 파일을 업로드하세요.")
        
        st.markdown("""
        ### 📖 사용 방법
        
        #### 방법 1: API로 데이터 수집
        1. 사이드바에서 **API 키** 입력
        2. **데이터 수집 시작** 버튼 클릭
        3. 수집 완료 후 자동으로 지도 표시
        
        #### 방법 2: CSV 파일 업로드
        1. 사이드바에서 **CSV 파일 선택**
        2. 업로드 완료 후 자동으로 지도 표시
        
        ### 🔧 환경변수 설정 (선택사항)
        
        `.env` 파일 생성:
        ```
        FARMER_KEY=your_api_key_here
        ```
        
        또는 시스템 환경변수로 설정:
        ```bash
        # Windows
        set FARMER_KEY=your_api_key_here
        
        # Mac/Linux
        export FARMER_KEY=your_api_key_here
        ```
        
        ### 필요한 라이브러리
        ```bash
        pip install streamlit pandas folium streamlit-folium plotly requests
        ```
        """)


if __name__ == "__main__":
    main()