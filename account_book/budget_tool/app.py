"""가계부 웹 앱 (Streamlit).

- 지출내역 폴더의 뱅크샐러드 파일들을 **연 단위로 중복 없이 자동 취합**한다.
- 좌측 사이드바에서 **연도 목차**로 이동한다.
- 취합 결과는 data/<년도>/ 에 CSV 작업본으로 저장되며 웹에서 편집·유지할 수 있다.
- 여러 해를 합쳐 연도 통합 추이를 분석한다.
로컬(localhost)에서만 구동된다.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import aggregate as agg
import ingest
import storage
from config import load_config, resolve_path

st.set_page_config(page_title="가계부", page_icon="📒", layout="wide")


def won(x) -> str:
    try:
        return f"{x:,.0f}원"
    except (TypeError, ValueError):
        return "-"


def won_df(df: pd.DataFrame, cols) -> pd.DataFrame:
    """지정한 금액 컬럼을 '1,234,567원' 문자열로 변환(표 가독성)."""
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].map(lambda v: f"{v:,.0f}원" if pd.notna(v) else "-")
    return out


def won_axis(fig, axis: str = "y", hover: bool = True):
    """플롯 값 축을 콤마 구분 + '원' 단위로, 호버도 동일하게."""
    fig.update_layout(separators=",.")
    if axis == "y":
        fig.update_yaxes(tickformat=",.0f", ticksuffix="원")
        tmpl = "%{fullData.name}: %{y:,.0f}원<extra></extra>"
    else:
        fig.update_xaxes(tickformat=",.0f", ticksuffix="원")
        tmpl = "%{fullData.name}: %{x:,.0f}원<extra></extra>"
    if hover:
        fig.update_traces(hovertemplate=tmpl)
    return fig


def won_hover_part(fig):
    """파이/선버스트용: 라벨 + 금액(원)."""
    fig.update_layout(separators=",.")
    fig.update_traces(hovertemplate="%{label}: %{value:,.0f}원<extra></extra>")
    return fig


def prep_editor(df: pd.DataFrame, text_cols=(), num_cols=(), date_cols=()):
    """data_editor 로 넘기기 전 컬럼 dtype 정규화 (전부 NaN 컬럼 타입 충돌 방지)."""
    df = df.copy()
    for c in text_cols:
        df[c] = df[c].fillna("").astype(str) if c in df.columns else ""
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else 0
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date if c in df.columns else pd.NaT
    return df


def compute_summary(data: dict, year: int) -> dict:
    mt = agg.monthly_totals(data["txns"], year)
    fs = agg.financial_state(data["assets"], data["liabilities"])
    return {
        "year": year,
        "monthly": mt.to_dict(orient="records"),
        "total_asset": fs["total_asset"],
        "total_liability": fs["total_liability"],
        "net_worth": fs["net_worth"],
    }


# ------------------------------------------------------ 폴더 취합 (캐시)
def folder_signature(export_dir: Path) -> tuple:
    if not export_dir.exists():
        return ()
    sig = []
    for p in sorted(export_dir.glob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        s = p.stat()
        sig.append((p.name, int(s.st_mtime), s.st_size))
    return tuple(sig)


@st.cache_data(show_spinner="지출내역 폴더를 취합하는 중...")
def load_ingest(export_dir_str: str, name_map_items: tuple, signature: tuple):
    return ingest.ingest_all(Path(export_dir_str), dict(name_map_items))


def seed_year(year: int, ing, overwrite: bool = False) -> None:
    if storage.working_exists(year) and not overwrite:
        return
    yt = ing.txns[ing.txns["year"] == year] if not ing.txns.empty else pd.DataFrame()
    snap = ingest.snapshot_for_year(ing.snapshots, year)
    data = {"txns": yt, "assets": snap["assets"],
            "liabilities": snap["liabilities"], "investments": snap["investments"]}
    storage.save_working(data, year)
    storage.save_summary(compute_summary(storage.load_working(year), year), year)


cfg = load_config()
export_dir = resolve_path(cfg.export_dir)
sig = folder_signature(export_dir)
ing = load_ingest(str(export_dir), tuple(sorted(cfg.user_names.items())), sig)
available_years = sorted(ing.txns["year"].unique().tolist()) if not ing.txns.empty else []

# 사용 가능한 모든 연도의 작업본을 자동 생성(없는 것만) → 추이/편집 즉시 가능
for y in available_years:
    seed_year(y, ing, overwrite=False)


# ------------------------------------------------------------------- 사이드바 (목차)
st.sidebar.title("📒 가계부")
if not available_years:
    st.sidebar.error("지출내역 폴더에서 파일을 찾지 못했습니다.")
    st.stop()

st.sidebar.markdown("### 📑 연도 목차")
year = st.sidebar.radio(
    "연도 선택", available_years, index=len(available_years) - 1,
    format_func=lambda y: f"{y}년", label_visibility="collapsed", key="year_sel",
)

st.sidebar.markdown(f"#### {year}년 원본 파일")
yfiles = ingest.files_for_year(ing.files, year)
if yfiles:
    for sf in yfiles:
        st.sidebar.caption("• " + sf.path.name)
else:
    st.sidebar.caption("(해당 연도 파일 없음)")

with st.sidebar.expander("🔄 폴더 새로고침 / 재동기화"):
    if st.button("폴더 새로고침 (신규 파일 반영)", width="stretch"):
        load_ingest.clear()
        st.rerun()
    st.caption("아래는 **선택 연도**의 편집 내용을 버리고 폴더에서 다시 만듭니다.")
    if st.button(f"♻️ {year}년 재동기화", width="stretch"):
        seed_year(year, ing, overwrite=True)
        st.success(f"{year}년 재동기화 완료")
        st.rerun()

if ing.warnings:
    with st.sidebar.expander("⚠️ 경고"):
        for w in ing.warnings:
            st.write("- " + w)
st.sidebar.caption(f"총 거래(중복제거): {len(ing.txns):,}건")


# ------------------------------------------------------------------- 데이터 로드
data = storage.load_working(year)
txns = data["txns"]
users = sorted(txns["user"].unique().tolist()) if not txns.empty else \
    list(cfg.user_names.values())

st.title(f"📒 {year}년 가계부")

tab_dash, tab_month, tab_pnl, tab_bs, tab_trend = st.tabs(
    ["📊 대시보드", "📅 월별 가계부", "📈 손익계산서", "🏦 재무상태표", "📉 연도 추이"]
)


# ------------------------------------------------------------------- 대시보드
with tab_dash:
    st.header("📊 대시보드")
    if txns.empty:
        st.info("이 연도에는 거래 데이터가 없습니다.")
    else:
        fs = agg.financial_state(data["assets"], data["liabilities"])
        mt = agg.monthly_totals(txns, year)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총자산", won(fs["total_asset"]))
        c2.metric("순자산", won(fs["net_worth"]))
        c3.metric(f"{year} 총수입", won(mt["수입"].sum()))
        c4.metric(f"{year} 총지출", won(mt["지출"].sum()))

        st.subheader("월별 현금 흐름")
        mplot = mt.copy()
        mplot["월"] = mplot["월"].astype(str) + "월"
        fig = go.Figure()
        fig.add_bar(x=mplot["월"], y=mplot["수입"], name="수입", marker_color="#4C9F70")
        fig.add_bar(x=mplot["월"], y=mplot["지출"], name="지출", marker_color="#D9534F")
        fig.add_scatter(x=mplot["월"], y=mplot["순이익"], name="순이익",
                        mode="lines+markers", line=dict(color="#3B6EA5", width=3))
        fig.update_layout(barmode="group", height=380, legend_orientation="h",
                          margin=dict(t=20, b=10))
        won_axis(fig, "y")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("사용자별 수입 / 지출 총계")
        ut = agg.user_totals(txns, year)
        colA, colB = st.columns([2, 3])
        with colA:
            st.dataframe(won_df(ut, ["수입", "지출", "순이익"]),
                         width="stretch", hide_index=True)
        with colB:
            plot_ut = ut[ut["사용자"] != "합계"]
            ubar = go.Figure()
            ubar.add_bar(x=plot_ut["사용자"], y=plot_ut["수입"], name="수입",
                         marker_color="#4C9F70")
            ubar.add_bar(x=plot_ut["사용자"], y=plot_ut["지출"], name="지출",
                         marker_color="#D9534F")
            ubar.update_layout(barmode="group", height=300, legend_orientation="h",
                               margin=dict(t=10, b=10))
            won_axis(ubar, "y")
            st.plotly_chart(ubar, use_container_width=True)

        colL, colR = st.columns(2)
        with colL:
            st.subheader("자산 구성")
            bg = fs["by_group"]
            if not bg.empty:
                pie = px.pie(bg, names="group", values="amount", hole=0.45)
                pie.update_layout(height=320, margin=dict(t=10, b=10))
                won_hover_part(pie)
                st.plotly_chart(pie, use_container_width=True)
        with colR:
            st.subheader("사용자별 순이익")
            per_user = [
                {"사용자": u, "순이익": agg.monthly_totals(
                    txns[txns["user"] == u], year)["순이익"].sum()}
                for u in users
            ]
            bar = px.bar(pd.DataFrame(per_user), x="사용자", y="순이익", color="사용자")
            bar.update_traces(texttemplate="%{y:,.0f}원", textposition="outside")
            bar.update_layout(height=320, margin=dict(t=10, b=10), showlegend=False)
            won_axis(bar, "y", hover=False)
            st.plotly_chart(bar, use_container_width=True)


# ------------------------------------------------------------------- 월별 가계부
with tab_month:
    st.header("📅 월별 가계부")
    if txns.empty:
        st.info("이 연도에는 거래 데이터가 없습니다.")
    else:
        col1, col2 = st.columns([1, 2])
        month = col1.selectbox("월 선택", range(1, 13),
                               format_func=lambda m: f"{m}월", key="month_sel")
        user_pick = col2.radio("사용자", ["전체"] + users, horizontal=True,
                               key="month_user")

        base = txns if user_pick == "전체" else txns[txns["user"] == user_pick]
        inc = base[(base["month"] == month) & (base["type"] == agg.INCOME)]["amount"].sum()
        exp = base[(base["month"] == month) & (base["type"] == agg.EXPENSE)]["amount"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("수입", won(inc))
        m2.metric("지출", won(abs(exp)))
        m3.metric("순이익", won(inc + exp))

        st.markdown(f"##### {month}월 사용자별 수입 / 지출 총계")
        ut_m = agg.user_totals(txns, year, month)
        st.dataframe(won_df(ut_m, ["수입", "지출", "순이익"]),
                     width="stretch", hide_index=True)

        st.markdown("##### 카테고리별 지출")
        cs = agg.category_summary(base, year, month, agg.EXPENSE)
        if not cs.empty:
            fig = px.bar(cs, x="금액", y="분류", orientation="h")
            fig.update_layout(height=max(250, 28 * len(cs)),
                              yaxis=dict(autorange="reversed"), margin=dict(t=10))
            won_axis(fig, "x", hover=False)
            fig.update_traces(hovertemplate="%{y}: %{x:,.0f}원<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### 거래 내역")
        cols = st.columns(3)
        for col, ttype in zip(cols, [agg.INCOME, agg.EXPENSE, agg.TRANSFER]):
            with col:
                st.caption(f"**{ttype}**")
                t = agg.monthly_table(base, year, month, ttype)
                st.dataframe(won_df(t, ["금액"]), width="stretch",
                             hide_index=True, height=300)

        # ---------------------------------------------------------- 편집
        st.divider()
        st.markdown("### ✏️ 거래 편집")
        if user_pick == "전체":
            st.info("편집하려면 위에서 **특정 사용자**를 선택하세요.")
        else:
            st.caption(
                f"**{user_pick}**님의 **{month}월** 거래입니다. 셀 수정 또는 "
                "행 추가/삭제 후 저장하세요."
            )
            mask = (txns["user"] == user_pick) & (txns["month"] == month)
            edit_cols = ["date", "type", "category", "subcategory",
                         "content", "amount", "pay", "memo"]
            subset = prep_editor(
                txns[mask][edit_cols],
                text_cols=["type", "category", "subcategory", "content", "pay", "memo"],
                num_cols=["amount"], date_cols=["date"],
            )
            edited = st.data_editor(
                subset, num_rows="dynamic", width="stretch", height=320,
                key=f"editor_{user_pick}_{month}",
                column_config={
                    "date": st.column_config.DateColumn("날짜"),
                    "type": st.column_config.SelectboxColumn(
                        "타입", options=[agg.INCOME, agg.EXPENSE, agg.TRANSFER]),
                    "category": st.column_config.TextColumn("분류"),
                    "subcategory": st.column_config.TextColumn("소분류"),
                    "content": st.column_config.TextColumn("내용"),
                    "amount": st.column_config.NumberColumn("금액", format="%d"),
                    "pay": st.column_config.TextColumn("결제수단"),
                    "memo": st.column_config.TextColumn("메모"),
                },
            )
            if st.button("💾 이 달 거래 저장", key=f"save_{user_pick}_{month}"):
                new_rows = edited.dropna(subset=["date"]).copy()
                new_rows.insert(0, "user", user_pick)
                rest = txns[~mask][storage.TXN_COLS]
                merged = pd.concat([rest, new_rows[storage.TXN_COLS]],
                                   ignore_index=True)
                storage.save_transactions(merged, year)
                storage.save_summary(
                    compute_summary(storage.load_working(year), year), year)
                st.success(f"{user_pick}님 {month}월 거래를 저장했습니다.")
                st.rerun()


# ------------------------------------------------------------------- 손익계산서
with tab_pnl:
    st.header("📈 손익계산서")
    if txns.empty:
        st.info("이 연도에는 거래 데이터가 없습니다.")
    else:
        month = st.selectbox("월", range(1, 13), format_func=lambda m: f"{m}월",
                             key="pnl_month")
        ist = agg.income_statement(txns, year, month)
        c1, c2, c3 = st.columns(3)
        c1.metric("수입", won(ist["income_total"]))
        c2.metric("지출", won(ist["expense_total"]))
        c3.metric("순이익", won(ist["net"]))

        cat = ist["categories"]
        st.markdown("##### 카테고리별 지출: 이번 달 vs 평균")
        if not cat.empty:
            top = cat.head(12)
            fig = go.Figure()
            fig.add_bar(y=top["분류"], x=top["이번달"], name="이번 달",
                        orientation="h", marker_color="#D9534F")
            fig.add_bar(y=top["분류"], x=top["평균"], name="평균",
                        orientation="h", marker_color="#B0B0B0")
            fig.update_layout(barmode="group", height=max(300, 32 * len(top)),
                              yaxis=dict(autorange="reversed"),
                              legend_orientation="h", margin=dict(t=10))
            won_axis(fig, "x")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### 상세 (평균 대비 증감)")
        show = cat.copy()
        show["평균대비"] = show["평균대비"].apply(
            lambda v: f"{v*100:+.0f}%" if v is not None and pd.notna(v) else "-"
        )
        show = won_df(show, ["이번달", "평균", "차이"])
        st.dataframe(show, width="stretch", hide_index=True)
        st.caption(f"평균은 데이터가 있는 {ist['n_months']}개월 기준입니다.")


# ------------------------------------------------------------------- 재무상태표
with tab_bs:
    st.header("🏦 재무상태표")
    fs = agg.financial_state(data["assets"], data["liabilities"])
    c1, c2, c3 = st.columns(3)
    c1.metric("총자산", won(fs["total_asset"]))
    c2.metric("총부채", won(fs["total_liability"]))
    c3.metric("순자산", won(fs["net_worth"]))

    colL, colR = st.columns(2)
    with colL:
        st.subheader("그룹별 자산")
        bg = fs["by_group"]
        if not bg.empty:
            st.dataframe(
                won_df(bg.rename(columns={"group": "그룹", "amount": "금액"}), ["금액"]),
                width="stretch", hide_index=True,
            )
        bi = fs["by_item"]
        if not bi.empty:
            sun = px.sunburst(bi, path=["group", "item"], values="amount")
            sun.update_layout(height=380, margin=dict(t=10, b=10))
            won_hover_part(sun)
            st.plotly_chart(sun, use_container_width=True)
    with colR:
        st.subheader("사용자별 순자산")
        rows = []
        for u in users:
            ua = data["assets"][data["assets"]["user"] == u]["amount"].sum() \
                if not data["assets"].empty else 0
            ul = data["liabilities"][data["liabilities"]["user"] == u]["amount"].sum() \
                if not data["liabilities"].empty else 0
            rows.append({"사용자": u, "자산": ua, "부채": ul, "순자산": ua - ul})
        st.dataframe(won_df(pd.DataFrame(rows), ["자산", "부채", "순자산"]),
                     width="stretch", hide_index=True)

    inv = data["investments"]
    if not inv.empty:
        st.subheader("투자 현황")
        iv = inv[inv["value"] > 0].copy()
        iv["손익"] = iv["value"] - iv["principal"]
        total_p, total_v = iv["principal"].sum(), iv["value"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("투자원금", won(total_p))
        m2.metric("평가금액", won(total_v))
        m3.metric("수익률", f"{(total_v/total_p-1)*100:+.1f}%" if total_p else "-")
        iv_show = (
            iv[["user", "name", "principal", "value", "손익", "ret"]]
            .rename(columns={"user": "사용자", "name": "종목", "principal": "원금",
                             "value": "평가금액", "ret": "수익률(%)"})
            .sort_values("평가금액", ascending=False)
        )
        iv_show["수익률(%)"] = iv_show["수익률(%)"].map(lambda v: f"{v:+.1f}%")
        st.dataframe(won_df(iv_show, ["원금", "평가금액", "손익"]),
                     width="stretch", hide_index=True)

    # ---------------------------------------------------------------- 편집
    st.divider()
    st.markdown("### ✏️ 자산 / 부채 편집")
    st.caption("실제 자산 흐름과 다르면 직접 수정·추가하세요. 저장하면 유지됩니다.")
    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown("**자산**")
        a_edit = st.data_editor(
            prep_editor(
                data["assets"].reindex(columns=storage.ASSET_COLS),
                text_cols=["user", "group", "item", "name"], num_cols=["amount"],
            ),
            num_rows="dynamic", width="stretch", height=360, key="assets_editor",
            column_config={
                "user": st.column_config.TextColumn("사용자"),
                "group": st.column_config.SelectboxColumn("그룹", options=["저축", "투자"]),
                "item": st.column_config.TextColumn("항목"),
                "name": st.column_config.TextColumn("상품명"),
                "amount": st.column_config.NumberColumn("금액", format="%d"),
            },
        )
    with ec2:
        st.markdown("**부채**")
        l_edit = st.data_editor(
            prep_editor(
                data["liabilities"].reindex(columns=storage.LIAB_COLS),
                text_cols=["user", "item", "name"], num_cols=["amount"],
            ),
            num_rows="dynamic", width="stretch", height=360, key="liab_editor",
            column_config={
                "user": st.column_config.TextColumn("사용자"),
                "item": st.column_config.TextColumn("항목"),
                "name": st.column_config.TextColumn("상품명"),
                "amount": st.column_config.NumberColumn("금액", format="%d"),
            },
        )
    if st.button("💾 자산/부채 저장"):
        storage.save_financial_state(a_edit, l_edit, data["investments"], year)
        storage.save_summary(
            compute_summary(storage.load_working(year), year), year)
        st.success("자산/부채를 저장했습니다.")
        st.rerun()


# ------------------------------------------------------------------- 연도 추이
with tab_trend:
    st.header("📉 연도 통합 추이")
    all_txns = storage.load_all_transactions()
    summaries = storage.load_all_summaries()
    saved_years = storage.list_saved_years()

    if all_txns.empty:
        st.info("저장된 데이터가 없습니다.")
    else:
        st.caption("저장된 모든 연도(" + ", ".join(map(str, saved_years)) +
                   ")의 데이터를 합쳐 표시합니다.")
        ts = agg.monthly_timeseries(all_txns)

        st.subheader("월별 수입 / 지출 / 순이익")
        fig = go.Figure()
        fig.add_bar(x=ts["연월"], y=ts["수입"], name="수입", marker_color="#4C9F70")
        fig.add_bar(x=ts["연월"], y=ts["지출"], name="지출", marker_color="#D9534F")
        fig.add_scatter(x=ts["연월"], y=ts["순이익"], name="순이익",
                        mode="lines+markers", line=dict(color="#3B6EA5", width=2))
        fig.update_layout(barmode="group", height=400, legend_orientation="h",
                          margin=dict(t=20, b=10))
        won_axis(fig, "y")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("누적 순이익")
        cum = ts.copy()
        cum["누적순이익"] = cum["순이익"].cumsum()
        line = px.area(cum, x="연월", y="누적순이익")
        line.update_layout(height=300, margin=dict(t=10, b=10))
        won_axis(line, "y")
        st.plotly_chart(line, use_container_width=True)

        colL, colR = st.columns(2)
        with colL:
            st.subheader("연도별 수입 / 지출")
            yearly = (
                all_txns.assign(
                    수입=lambda d: d["amount"].where(d["type"] == agg.INCOME, 0),
                    지출=lambda d: d["amount"].where(d["type"] == agg.EXPENSE, 0).abs(),
                ).groupby("year")[["수입", "지출"]].sum().reset_index()
            )
            yearly["순이익"] = yearly["수입"] - yearly["지출"]
            fig2 = px.bar(yearly, x="year", y=["수입", "지출"], barmode="group")
            fig2.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="연도")
            won_axis(fig2, "y")
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(won_df(yearly, ["수입", "지출", "순이익"]),
                         width="stretch", hide_index=True)
        with colR:
            st.subheader("연도별 순자산 스냅샷")
            if not summaries.empty:
                fig3 = go.Figure()
                fig3.add_scatter(x=summaries["year"], y=summaries["total_asset"],
                                 name="총자산", mode="lines+markers")
                fig3.add_scatter(x=summaries["year"], y=summaries["net_worth"],
                                 name="순자산", mode="lines+markers")
                fig3.update_layout(height=320, margin=dict(t=10, b=10),
                                   xaxis_title="연도", legend_orientation="h")
                won_axis(fig3, "y")
                st.plotly_chart(fig3, use_container_width=True)
                st.dataframe(
                    won_df(summaries.rename(columns={
                        "year": "연도", "total_asset": "총자산",
                        "total_liability": "총부채", "net_worth": "순자산"}),
                        ["총자산", "총부채", "순자산"]),
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("순자산 스냅샷이 없습니다.")
