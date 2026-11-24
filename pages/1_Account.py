from __future__ import annotations

import streamlit as st

from services.account import AccountService, normalize_church_name
from services.auth import AuthService
from services.supabase import SupabaseError
from ui import configured_client, current_profile, finish_oauth, save_session, show_error


st.set_page_config(page_title="Account · Herald", page_icon="👤", layout="wide")
st.title("Account and church")
client = configured_client()
if client is None:
    st.stop()
finish_oauth(client)

if client.session is None:
    st.write("Sign in to access the private song catalog and community.")
    tab_password, tab_oauth, tab_signup = st.tabs(["Email and password", "Google / Microsoft", "Create account"])
    with tab_password:
        with st.form("password_sign_in"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                AuthService(client).sign_in(email, password)
                save_session(client)
                st.rerun()
            except (ValueError, SupabaseError) as exc:
                show_error(exc)
    with tab_oauth:
        redirect_url = st.text_input("OAuth redirect URL", value=st.session_state.get("oauth_redirect", ""))
        for provider, label in (("google", "Google"), ("azure", "Microsoft")):
            if st.button(f"Continue with {label}", key=f"oauth_{provider}"):
                try:
                    url, verifier = AuthService(client).oauth_url(provider, redirect_url)
                    st.session_state["oauth_verifier"] = verifier
                    st.session_state["oauth_redirect"] = redirect_url
                    st.link_button(f"Open {label}", url, type="primary")
                except ValueError as exc:
                    show_error(exc)
        st.caption("Register this exact Streamlit URL as an allowed redirect URL in Supabase Auth.")
    with tab_signup:
        with st.form("signup"):
            name = st.text_input("Display name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            redirect_url = st.text_input("Confirmation redirect URL", key="signup_redirect")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                AuthService(client).sign_up(email, password, name, redirect_url)
                st.success("Check your email to confirm the account, then sign in.")
            except SupabaseError as exc:
                show_error(exc)
    st.stop()

st.success(f"Signed in as {client.session.user.get('email') or client.session.user_id}")
if st.button("Sign out"):
    try:
        client.sign_out()
    finally:
        save_session(client)
    st.rerun()

profile = current_profile(client)
account = AccountService(client)
if profile and profile.get("onboarding_completed_at"):
    st.subheader("Church profile")
    st.write(f"**Display name:** {profile.get('display_name') or 'Not set'}")
    try:
        path = account.church_path(str(profile["church_node_id"]))
    except SupabaseError as exc:
        show_error(exc)
        path = []
    if path:
        st.write(" / ".join(str(node["name"]) for node in path))
    st.info("Your church path is complete. Moderators and RLS policies govern all protected actions.")
    st.stop()

st.subheader("Complete your church profile")
st.write("Choose the existing canonical organization and each existing node before creating a new path.")
display_name = st.text_input("Display name", value=(profile or {}).get("display_name") or "")

search = st.text_input("Main church / organization", key="org_search")
if st.button("Find organizations", disabled=len(search.strip()) < 2):
    st.session_state["org_choices"] = account.organizations(search)
    st.session_state.pop("selected_org", None)

org_choices = st.session_state.get("org_choices", [])
selected_org = st.session_state.get("selected_org")
if org_choices and not selected_org:
    exact = [row for row in org_choices if normalize_church_name(row["name"]) == normalize_church_name(search)]
    if exact:
        st.success(f"Exact canonical match: **{exact[0]['name']}**")
    labels = [row["name"] for row in org_choices]
    choice = st.selectbox("Existing organizations (best matches first)", labels, index=None)
    if choice:
        selected_org = next(row for row in org_choices if row["name"] == choice)
        st.session_state["selected_org"] = selected_org

create_col, use_col = st.columns([2, 1])
with create_col:
    new_org_name = st.text_input("Create a genuinely new organization (canonical names are reused)", value=search)
with use_col:
    if st.button("Use or create organization"):
        try:
            selected_org = account.create_or_find_organization(new_org_name)
            st.session_state["selected_org"] = selected_org
            st.rerun()
        except SupabaseError as exc:
            show_error(exc)

selected_org = st.session_state.get("selected_org")
if not selected_org:
    st.stop()

st.markdown(f"### {selected_org['name']}")
organization_id = str(selected_org["id"])
levels = account.hierarchy_levels(organization_id)
if not levels:
    st.warning("This organization has no configured hierarchy levels.")
    st.write("Only its creator or a moderator can add levels through the database-enforced RPC.")
    hierarchy_labels = st.text_area(
        "Hierarchy labels, one per line, from broadest to most local",
        placeholder="Country\nRegion\nDistrict\nLocal church",
    )
    if st.button("Create hierarchy levels"):
        labels = [item.strip() for item in hierarchy_labels.splitlines() if item.strip()]
        try:
            for order, label in enumerate(labels, start=1):
                account.add_hierarchy_level(organization_id, label, order)
            st.rerun()
        except SupabaseError as exc:
            show_error(exc)
    st.stop()

node_path = []
for index, level in enumerate(levels):
    parent = node_path[-1] if node_path else None
    parent_id = str(parent["id"]) if parent else None
    existing = account.nodes(organization_id, str(level["id"]), parent_id)
    st.write(f"#### {level['label']}")
    query = st.text_input(f"{level['label']} name", key=f"node_query_{level['id']}")
    normalized = normalize_church_name(query)
    ranked = sorted(
        existing,
        key=lambda row: (
            normalize_church_name(row["name"]) != normalized,
            normalize_church_name(row["name"]),
        ),
    )
    exact = next((row for row in ranked if normalize_church_name(row["name"]) == normalized), None)
    if exact and query:
        st.success(f"Exact canonical match: **{exact['name']}**")
    options = [f"{row['name']}  ·  {row['id']}" for row in ranked]
    choice = st.selectbox(
        f"Choose an existing {level['label']}",
        options,
        index=None,
        key=f"node_choice_{level['id']}",
    )
    selected = next((row for row in ranked if f"{row['name']}  ·  {row['id']}" == choice), None)
    if selected:
        node_path.append(selected)
        continue
    if query and st.button(f"Create or find this {level['label']}", key=f"create_node_{level['id']}"):
        created = account.create_or_find_node(organization_id, str(level["id"]), parent_id, query)
        st.session_state[f"node_created_{level['id']}"] = created
        st.rerun()
    created = st.session_state.get(f"node_created_{level['id']}")
    if created and created.get("parent_id") == parent_id:
        node_path.append(created)
        continue
    st.info("Select or create this node to continue to the next hierarchy level.")
    st.stop()

st.success(" / ".join([selected_org["name"], *(node["name"] for node in node_path)]))
if st.button("Complete church profile", type="primary"):
    try:
        account.complete_profile(str(node_path[-1]["id"]), display_name)
        st.session_state.pop("selected_org", None)
        st.rerun()
    except (SupabaseError, ValueError) as exc:
        show_error(exc)
