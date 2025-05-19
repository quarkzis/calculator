import streamlit as st
import pandas as pd
import plotly.express as px

# Page configuration
st.set_page_config(
    page_title="EUDR Due Diligence Costs Calculator",
    page_icon="💼",
    layout="wide"
)

# Main title
st.title("EUDR Due Diligence Costs Calculator")

# Primary filter: Setup vs Ongoing costs
cost_type = st.radio(
    "Select Cost Type",
    ["SET UP COSTS", "ON-GOING COSTS", "BOTH"],
    horizontal=True
)

# Define tasks for each cost type with codes
setup_tasks = [
    {"code": "S1", "name": "Develop detailed EUDR due diligence compliance framework (Art. 12)"},
    {"code": "S2", "name": "Establish information/data systems for EUDR compliance (Art. 12)"},
    {"code": "S3", "name": "Conduct staff training and ensure sufficient capacity to manage EUDR compliance (Art. 12)"},
    {"code": "S4", "name": "Investigate and confirm product scope (HS Codes/ingredients) (Art. 9)"},
    {"code": "S5", "name": "Information collection (Art. 9)"},
    {"code": "S6", "name": "Conduct initial risk assessments (Art. 10)"},
    {"code": "S7", "name": "Risk mitigation (Art. 11)"},
    {"code": "S8", "name": "Submit initial DDS for existing products/batches (Art. 3)"}
]

ongoing_tasks = [
    {"code": "O1", "name": "Review and update due diligence procedures (Art. 12)"},
    {"code": "O2", "name": "Review and update IT information data systems (Art. 12)"},
    {"code": "O3", "name": "Refresher training to existing staff and training to new staff (Art. 12)"},
    {"code": "O4", "name": "Maintain/update supply chain information and documentation (Art. 9)"},
    {"code": "O5", "name": "Maintain risk assessments (Art. 10)"},
    {"code": "O6", "name": "Maintain risk mitigation (Art. 11)"},
    {"code": "O7", "name": "Continuously submit DDS for new product batches (Art. 3)"},
    {"code": "O8", "name": "Maintain and enhance DDS submission system (Art. 3)"}
]

# Define positions and their daily rates
st.header("Daily Rates by Position")
daily_rates = {
    "SO": st.number_input("Sustainability Officer (£/day)", min_value=0, value=600, step=50),
    "LAW": st.number_input("Lawyer (£/day)", min_value=0, value=800, step=50),
    "PM": st.number_input("Procurement/Technical Manager (£/day)", min_value=0, value=700, step=50),
    "AA": st.number_input("Administrative Assistant (£/day)", min_value=0, value=300, step=50),
    "IT": st.number_input("IT Professional (£/day)", min_value=0, value=500, step=50),
    "EC": st.number_input("External Consultant (£/day)", min_value=0, value=1000, step=50),
}

# Adjust visible tasks based on selected cost type
active_tasks = []
if cost_type == "SET UP COSTS":
    active_tasks = setup_tasks
    st.header("SET UP COSTS - Task Assignment")
elif cost_type == "ON-GOING COSTS":
    active_tasks = ongoing_tasks
    st.header("ON-GOING COSTS - Task Assignment")
else:  # BOTH
    active_tasks = setup_tasks + ongoing_tasks
    st.header("SET UP COSTS - Task Assignment")

# Function to create task assignment UI
def create_task_assignment(tasks, task_prefix):
    task_assignments = {}
    
    for task in tasks:
        task_code = task["code"]
        task_name = task["name"]
        st.subheader(f"{task_code}: {task_name}")
        cols = st.columns(6)
        
        task_assignments[task_code] = {
            "name": task_name,
            "positions": {}
        }
        
        for i, position in enumerate(["SO", "LAW", "PM", "AA", "IT", "EC"]):
            with cols[i]:
                days = st.number_input(
                    f"{position} days", 
                    min_value=0.0, 
                    value=1.0, 
                    step=0.5,
                    key=f"{task_prefix}_{task_code}_{position}"
                )
                task_assignments[task_code]["positions"][position] = days
    
    return task_assignments

# Initialize task assignments dictionary
task_assignments = {}

# Show appropriate task assignments based on selection
if cost_type == "SET UP COSTS" or cost_type == "BOTH":
    setup_assignments = create_task_assignment(setup_tasks, "setup")
    task_assignments.update(setup_assignments)

if cost_type == "ON-GOING COSTS" or cost_type == "BOTH":
    if cost_type == "BOTH":
        st.header("ON-GOING COSTS - Task Assignment")
    ongoing_assignments = create_task_assignment(ongoing_tasks, "ongoing")
    task_assignments.update(ongoing_assignments)

# Calculate base costs
base_costs_by_task_position = {}
position_totals = {"SO": 0, "LAW": 0, "PM": 0, "AA": 0, "IT": 0, "EC": 0}
task_totals = {}
task_categories = {}

for task_code, task_data in task_assignments.items():
    task_name = task_data["name"]
    positions = task_data["positions"]
    
    base_costs_by_task_position[task_code] = {}
    task_total = 0
    
    # Determine if this is a setup or ongoing task
    is_setup = task_code.startswith("S")
    task_categories[task_code] = "SET UP COSTS" if is_setup else "ON-GOING COSTS"
    
    for position, days in positions.items():
        cost = days * daily_rates[position]
        base_costs_by_task_position[task_code][position] = cost
        position_totals[position] += cost
        task_total += cost
    
    task_totals[task_code] = task_total

total_base_cost = sum(task_totals.values())

# Adjustment factors section
st.header("Adjustment Factors")

col1, col2 = st.columns(2)

with col1:
    # Company type
    st.subheader("Company Type")
    
    # Default company types and factors
    default_company_types = {
        "Upstream operator (non-SME)": 1.00,
        "Upstream operator (SME)": 0.66,
        "Downstream operator (non-SME)": 0.75,
        "Downstream operator (SME)": 0.50,
        "Trader (non-SME)": 0.75,
        "Trader (SME)": 0.50,
    }
    
    company_type = st.selectbox("Select company type", list(default_company_types.keys()))
    default_factor = default_company_types[company_type]
    
    # Add ability to edit the factor
    company_factor = st.number_input(
        "Company type factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_factor, 
        step=0.01,
        format="%.2f",
        key="company_factor"
    )
    
    # Due diligence compliance
    st.subheader("Due Diligence Compliance")
    
    default_dd_compliance_types = {
        "No due diligence": 1.00,
        "Partial due diligence": 0.25,
        "Full due diligence": 0.75,
    }
    
    dd_compliance = st.selectbox("Select compliance level", list(default_dd_compliance_types.keys()))
    default_dd_factor = default_dd_compliance_types[dd_compliance]
    
    # Add ability to edit the factor
    dd_compliance_factor = st.number_input(
        "Due diligence factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_dd_factor, 
        step=0.01,
        format="%.2f",
        key="dd_factor"
    )
    
    # Source country
    st.subheader("Risk Level in Source Country")
    
    default_risk_types = {
        "Low risk country": 0.00,
        "High/Standard risk country": 1.00,
    }
    
    risk_type = st.selectbox("Select risk level", list(default_risk_types.keys()))
    default_risk_factor = default_risk_types[risk_type]
    
    # Add ability to edit the factor
    risk_factor = st.number_input(
        "Country risk factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_risk_factor, 
        step=0.01,
        format="%.2f",
        key="risk_factor"
    )

with col2:
    # Supply chain complexity
    st.subheader("Supply Chain Complexity")
    
    default_supply_chain_types = {
        "Simple supply chain": 0.75,
        "Standard supply chain": 1.00,
        "Complex supply chain": 2.00,
    }
    
    supply_chain = st.selectbox("Select complexity", list(default_supply_chain_types.keys()))
    default_supply_chain_factor = default_supply_chain_types[supply_chain]
    
    # Add ability to edit the factor
    supply_chain_factor = st.number_input(
        "Supply chain factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_supply_chain_factor, 
        step=0.01,
        format="%.2f",
        key="supply_chain_factor"
    )
    
    # Quantity of commodities
    st.subheader("Quantity of Commodities")
    commodity_count = st.slider("Select number of commodities", min_value=1, max_value=10, value=1, step=1)
    
    # Calculate default factor based on commodity count
    if commodity_count == 1:
        default_commodity_factor = 1.00
    else:
        default_commodity_factor = 1.00 + 0.25 * (commodity_count - 1)
    
    # Add ability to edit the factor
    commodity_factor = st.number_input(
        "Commodity factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_commodity_factor, 
        step=0.01,
        format="%.2f",
        key="commodity_factor"
    )

# Calculate the final adjusted cost sequentially
adjusted_cost_step1 = total_base_cost * company_factor
adjusted_cost_step2 = adjusted_cost_step1 * dd_compliance_factor
adjusted_cost_step3 = adjusted_cost_step2 * supply_chain_factor
adjusted_cost_step4 = adjusted_cost_step3 * commodity_factor
adjusted_cost = adjusted_cost_step4 * (1 + risk_factor)

# Display results
st.header("Budget Results")

# Create detailed cost breakdown by task and position
detailed_data = []
for task_code, task_data in task_assignments.items():
    task_name = task_data["name"]
    positions = task_data["positions"]
    
    for position in ["SO", "LAW", "PM", "AA", "IT", "EC"]:
        if position in positions and positions[position] > 0:
            cost = positions[position] * daily_rates[position]
            detailed_data.append({
                "Task Code": task_code,
                "Task": task_name,
                "Position": position,
                "Work Days": positions[position],
                "Daily Rate (£)": daily_rates[position],
                "Cost (£)": cost,
                "Category": task_categories[task_code]
            })

detailed_df = pd.DataFrame(detailed_data)

# Create task summary
task_summary = []
for task_code in task_totals:
    task_summary.append({
        "Task Code": task_code,
        "Task": task_assignments[task_code]["name"],
        "Category": task_categories[task_code],
        "Total Cost (£)": task_totals[task_code]
    })

task_summary_df = pd.DataFrame(task_summary)

# Create position summary
position_summary = []
for position in position_totals:
    position_summary.append({
        "Position": position,
        "Total Cost (£)": position_totals[position]
    })

position_summary_df = pd.DataFrame(position_summary)

# Display the results
col1, col2 = st.columns(2)

with col1:
    st.subheader("Detailed Cost Breakdown")
    st.dataframe(detailed_df, use_container_width=True)
    
    st.subheader("Task Summary")
    st.dataframe(task_summary_df, use_container_width=True)
    
    # Show applied factors
    factors_data = [
        {"Factor": "Company Type", "Value": f"{company_factor:.2f}", "Description": company_type},
        {"Factor": "Due Diligence Compliance", "Value": f"{dd_compliance_factor:.2f}", "Description": dd_compliance},
        {"Factor": "Supply Chain Complexity", "Value": f"{supply_chain_factor:.2f}", "Description": supply_chain},
        {"Factor": "Commodity Count", "Value": f"{commodity_factor:.2f}", "Description": f"{commodity_count} commodities"},
        {"Factor": "Country Risk Level", "Value": f"+{risk_factor:.2f}", "Description": risk_type},
    ]
    factors_df = pd.DataFrame(factors_data)
    st.dataframe(factors_df, use_container_width=True)

with col2:
    # Position summary pie chart
    fig1 = px.pie(
        position_summary_df,
        values="Total Cost (£)",
        names="Position",
        title="Cost Distribution by Position",
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    st.plotly_chart(fig1, use_container_width=True)
    
    # Task summary bar chart
    fig2 = px.bar(
        task_summary_df,
        x="Task Code",
        y="Total Cost (£)",
        title="Cost Distribution by Task",
        hover_data=["Task"],
        color="Category",
        color_discrete_map={"SET UP COSTS": "#1f77b4", "ON-GOING COSTS": "#ff7f0e"},
        category_orders={"Category": ["SET UP COSTS", "ON-GOING COSTS"]}
    )
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)
    
    # Create category summary
    category_summary = task_summary_df.groupby('Category')['Total Cost (£)'].sum().reset_index()
    
    # Create category pie chart
    fig3 = px.pie(
        category_summary,
        values="Total Cost (£)",
        names="Category",
        title="Cost Distribution by Category",
        color="Category",
        color_discrete_map={"SET UP COSTS": "#1f77b4", "ON-GOING COSTS": "#ff7f0e"}
    )
    st.plotly_chart(fig3, use_container_width=True)

# Show total costs in a more organized way
st.header("Cost Summary")
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Base Cost (Before Adjustments)", f"£{total_base_cost:,.2f}")
with col2:
    st.metric(
        "Final Adjusted Cost", 
        f"£{adjusted_cost:,.2f}", 
        delta=f"{((adjusted_cost/total_base_cost)-1)*100:.1f}%" if total_base_cost > 0 else "0%"
    )

# Detailed breakdown
st.header("Detailed Calculation Breakdown")
with st.expander("View detailed calculation breakdown"):
    st.markdown(f"""
    ### Base Cost
    - **Total Base Cost**: £{total_base_cost:,.2f}
    
    ### Sequential Factor Application
    1. **Base Cost**: £{total_base_cost:,.2f}
    2. **Company Type Adjustment** ({company_type}): £{total_base_cost:,.2f} × {company_factor:.2f} = £{adjusted_cost_step1:,.2f}
    3. **Compliance Adjustment** ({dd_compliance}): £{adjusted_cost_step1:,.2f} × {dd_compliance_factor:.2f} = £{adjusted_cost_step2:,.2f}
    4. **Complexity Adjustment** ({supply_chain}): £{adjusted_cost_step2:,.2f} × {supply_chain_factor:.2f} = £{adjusted_cost_step3:,.2f}
    5. **Commodities Adjustment** ({commodity_count}): £{adjusted_cost_step3:,.2f} × {commodity_factor:.2f} = £{adjusted_cost_step4:,.2f}
    6. **Country Risk Adjustment** ({risk_type}): £{adjusted_cost_step4:,.2f} × (1 + {risk_factor:.2f}) = £{adjusted_cost:,.2f}
    
    ### Final Adjusted Cost: £{adjusted_cost:,.2f}
    """)

# Show detailed task breakdown
st.subheader("Detailed Task Breakdown")
st.dataframe(detailed_df, use_container_width=True)

# Add section to download results
st.header("Download Results")

# Prepare data for download
def create_download_data():
    # Create a dictionary of DataFrames
    data = {
        "Summary": pd.DataFrame([
            {"Information": "Calculation Date", "Value": f"{pd.Timestamp.now().strftime('%Y-%m-%d')}"},
            {"Information": "Cost Type", "Value": cost_type},
            {"Information": "Total Base Cost (Before Adjustments)", "Value": f"£{total_base_cost:,.2f}"},
            {"Information": "Final Adjusted Cost", "Value": f"£{adjusted_cost:,.2f}"}
        ]),
        "Applied_Factors": pd.DataFrame(factors_data),
        "Calculation_Steps": pd.DataFrame([
            {"Step": "Base Cost", "Value": f"£{total_base_cost:,.2f}"},
            {"Step": f"Company Type Adjustment ({company_type})", "Value": f"£{adjusted_cost_step1:,.2f}"},
            {"Step": f"Compliance Adjustment ({dd_compliance})", "Value": f"£{adjusted_cost_step2:,.2f}"},
            {"Step": f"Complexity Adjustment ({supply_chain})", "Value": f"£{adjusted_cost_step3:,.2f}"},
            {"Step": f"Commodities Adjustment ({commodity_count})", "Value": f"£{adjusted_cost_step4:,.2f}"},
            {"Step": f"Country Risk Adjustment ({risk_type})", "Value": f"£{adjusted_cost:,.2f}"}
        ]),
        "Detailed_Costs": detailed_df,
        "Task_Summary": task_summary_df, 
        "Category_Summary": category_summary,
        "Position_Summary": position_summary_df
    }
    return data

# Button to download as CSV
if st.button("Generate CSV Report"):
    data = create_download_data()
    
    # Create Excel-style sheets in a single CSV by adding headers and separating sections
    sections = []
    
    # Summary section
    sections.append("===== SUMMARY =====")
    sections.append(data["Summary"].to_csv(index=False))
    sections.append("\n")
    
    # Factors section
    sections.append("===== APPLIED FACTORS =====")
    sections.append(data["Applied_Factors"].to_csv(index=False))
    sections.append("\n")
    
    # Calculation steps section
    sections.append("===== CALCULATION STEPS =====")
    sections.append(data["Calculation_Steps"].to_csv(index=False))
    sections.append("\n")
    
    # Category summary section
    sections.append("===== CATEGORY SUMMARY =====")
    sections.append(data["Category_Summary"].to_csv(index=False))
    sections.append("\n")
    
    # Position summary section
    sections.append("===== POSITION SUMMARY =====")
    sections.append(data["Position_Summary"].to_csv(index=False))
    sections.append("\n")
    
    # Task summary section
    sections.append("===== TASK SUMMARY =====")
    sections.append(data["Task_Summary"].to_csv(index=False))
    sections.append("\n")
    
    # Detailed costs section
    sections.append("===== DETAILED COSTS =====")
    sections.append(data["Detailed_Costs"].to_csv(index=False))
    
    # Join all sections
    csv_content = "\n".join(sections)
    
    st.download_button(
        label="Download CSV Report",
        data=csv_content,
        file_name=f"eudr_due_diligence_budget_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

# Final informational note
st.info("""
This calculator provides an estimate of the budget required to establish and maintain a due diligence system,
report annually, and keep records based on the selected factors. Values can be adjusted according to specific needs in each case.
""")