import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px

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

# 타이틀
st.title("🌱 전국 텃밭 정보 지도")
st.markdown("---")

# 파일 업로드
uploaded_file = st.file_uploader(
    "CSV 파일을 업로드하세요 (텃밭정보_전체데이터.csv)", 
    type=['csv']
)

if uploaded_file is not None:
    # CSV 파일 읽기
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        st.success(f"✅ 데이터 로드 완료: {len(df)}개")
        
        # 데이터 전처리
        df['PRICE'] = pd.to_numeric(df['PRICE'], errors='coerce').fillna(0)
        df['POSLAT'] = pd.to_numeric(df['POSLAT'], errors='coerce')
        df['POSLNG'] = pd.to_numeric(df['POSLNG'], errors='coerce')
        
        # 유효한 좌표만 필터링
        df_valid = df.dropna(subset=['POSLAT', 'POSLNG'])
        
        # 사이드바 필터
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
            # 지도 생성
            if not df_filtered.empty:
                # 중심 좌표
                center_lat = df_filtered['POSLAT'].mean()
                center_lng = df_filtered['POSLNG'].mean()
                
                # Folium 지도
                m = folium.Map(
                    location=[center_lat, center_lng],
                    zoom_start=8,
                    tiles='OpenStreetMap'
                )
                
                # 가격별 색상 함수
                def get_color(price):
                    if price <= 20:
                        return 'green'
                    elif price <= 40:
                        return 'orange'
                    elif price <= 60:
                        return 'red'
                    else:
                        return 'darkred'
                
                # 마커 추가
                for idx, row in df_filtered.iterrows():
                    popup_html = f"""
                    <div style="width: 280px; font-family: sans-serif;">
                        <h4 style="color: #667eea; margin: 0 0 10px 0;">{row['FARM_NM']}</h4>
                        <p style="margin: 5px 0;"><b>📍 주소:</b> {row['ADDRESS1']}</p>
                        <p style="margin: 5px 0;"><b>💰 가격:</b> {row['PRICE']}만원</p>
                        <p style="margin: 5px 0;"><b>📐 면적:</b> {row.get('SELL_AREA_INFO', '-')}㎡</p>
                        <p style="margin: 5px 0;"><b>🏢 운영:</b> {row.get('FARM_TYPE', '-')}</p>
                        <p style="margin: 5px 0;"><b>📅 모집:</b> {row.get('COLLEC_PROD', '-')}</p>
                        <p style="margin: 5px 0;"><b>✅ 신청:</b> {row.get('APPLY_MTHD', '-')}</p>
                    </div>
                    """
                    
                    folium.CircleMarker(
                        location=[row['POSLAT'], row['POSLNG']],
                        radius=8,
                        popup=folium.Popup(popup_html, max_width=300),
                        color=get_color(row['PRICE']),
                        fill=True,
                        fillColor=get_color(row['PRICE']),
                        fillOpacity=0.7,
                        weight=2
                    ).add_to(m)
                
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
                
                # 지도 표시
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
                file_name="필터링된_텃밭정보.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}")

else:
    # 파일이 업로드되지 않은 경우
    st.info("👆 CSV 파일을 업로드하면 지도와 통계를 확인할 수 있습니다.")
    
    st.markdown("""
    ### 사용 방법
    1. **텃밭정보_전체데이터.csv** 파일을 업로드하세요
    2. 사이드바에서 지역, 가격, 면적 필터를 설정하세요
    3. 지도 탭에서 텃밭 위치를 확인하세요
    4. 통계 탭에서 다양한 분석 차트를 확인하세요
    5. 데이터 탭에서 상세 정보를 확인하고 다운로드하세요
    
    ### 필요한 라이브러리
    ```bash
    pip install streamlit pandas folium streamlit-folium plotly
    ```
    
    ### 실행 방법
    ```bash
    streamlit run run_02.py
    ```
    """)