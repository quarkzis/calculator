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
    ["SET UP COSTS", "ON-GOING COSTS", "BOTH COSTS"],
    horizontal=True
)

# Define tasks for each cost type with codes, default values for each role, and company type factors
setup_tasks = [
    {
        "code": "S1", 
        "name": "Develop detailed EUDR due diligence compliance framework (Art. 12)",
        "defaults": {"SO": 30.0, "LAW": 5.0, "PM": 0.0, "AA": 0.0, "IT": 0.0, "EC": 3.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S2", 
        "name": "Establish information/data systems for EUDR compliance (Art. 12)",
        "defaults": {"SO": 8.0, "LAW": 0.0, "PM": 0.0, "AA": 5.0, "IT": 30.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S3", 
        "name": "Conduct staff training and ensure sufficient capacity to manage EUDR compliance (Art. 12)",
        "defaults": {"SO": 10.0, "LAW": 0.0, "PM": 7.0, "AA": 1.5, "IT": 1.5, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S4", 
        "name": "Investigate and confirm product scope (HS Codes/ingredients) (Art. 9)",
        "defaults": {"SO": 3.0, "LAW": 0.0, "PM": 0.0, "AA": 0.0, "IT": 0.0, "EC": 1.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S5", 
        "name": "Information collection (Art. 9)",
        "defaults": {"SO": 20.0, "LAW": 0.0, "PM": 20.0, "AA": 10.0, "IT": 5.0, "EC": 5.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S6", 
        "name": "Conduct initial risk assessments (Art. 10)",
        "defaults": {"SO": 8.0, "LAW": 0.0, "PM": 5.0, "AA": 0.0, "IT": 0.0, "EC": 2.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.50,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.50,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S7", 
        "name": "Risk mitigation (Art. 11)",
        "defaults": {"SO": 16.0, "LAW": 3.0, "PM": 12.0, "AA": 0.0, "IT": 0.0, "EC": 4.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.50,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.50,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "S8", 
        "name": "Submit initial DDS for existing products/batches (Art. 3)",
        "defaults": {"SO": 2.0, "LAW": 0.0, "PM": 0.0, "AA": 3.0, "IT": 1.0, "EC": 2.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 1.00,
            "Downstream operator (SME)": 0.00,
            "Trader (non-SME)": 1.00,
            "Trader (SME)": 1.00
        }
    }
]

ongoing_tasks = [
    {
        "code": "O1", 
        "name": "Review and update due diligence procedures (Art. 12)",
        "defaults": {"SO": 5.0, "LAW": 2.0, "PM": 0.0, "AA": 0.0, "IT": 0.0, "EC": 2.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O2", 
        "name": "Review and update IT information data systems (Art. 12)",
        "defaults": {"SO": 2.0, "LAW": 0.0, "PM": 0.0, "AA": 1.0, "IT": 6.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O3", 
        "name": "Refresher training to existing staff and training to new staff (Art. 12)",
        "defaults": {"SO": 10.0, "LAW": 0.0, "PM": 7.0, "AA": 1.5, "IT": 1.5, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.75,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O4", 
        "name": "Maintain/update supply chain information and documentation (Art. 9)",
        "defaults": {"SO": 15.0, "LAW": 0.0, "PM": 10.0, "AA": 10.0, "IT": 0.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.50,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O5", 
        "name": "Maintain risk assessments (Art. 10)",
        "defaults": {"SO": 6.0, "LAW": 0.0, "PM": 4.0, "AA": 0.0, "IT": 0.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.50,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O6", 
        "name": "Maintain risk mitigation (Art. 11)",
        "defaults": {"SO": 8.0, "LAW": 0.0, "PM": 7.0, "AA": 0.0, "IT": 0.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 0.75,
            "Downstream operator (SME)": 0.50,
            "Trader (non-SME)": 0.50,
            "Trader (SME)": 0.25
        }
    },
    {
        "code": "O7", 
        "name": "Continuously submit DDS for new product batches (Art. 3)",
        "defaults": {"SO": 2.0, "LAW": 0.0, "PM": 0.0, "AA": 3.0, "IT": 1.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 1.00,
            "Downstream operator (SME)": 0.00,
            "Trader (non-SME)": 1.00,
            "Trader (SME)": 0.00
        }
    },
    {
        "code": "O8", 
        "name": "Maintain and enhance DDS submission system (Art. 3)",
        "defaults": {"SO": 1.0, "LAW": 0.0, "PM": 0.0, "AA": 0.0, "IT": 3.0, "EC": 0.0},
        "company_type_factors": {
            "Upstream operator (non-SME)": 1.00,
            "Upstream operator (SME)": 1.00,
            "Downstream operator (non-SME)": 1.00,
            "Downstream operator (SME)": 0.00,
            "Trader (non-SME)": 1.00,
            "Trader (SME)": 0.00
        }
    }
]

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

# Define positions and their daily rates
st.header("Daily Rates by Position")
daily_rates = {
    "SO": st.number_input("Sustainability Officer (£/day)", min_value=0, value=238, step=1),
    "LAW": st.number_input("Lawyer (£/day)", min_value=0, value=268, step=1),
    "PM": st.number_input("Procurement/Technical Manager (£/day)", min_value=0, value=224, step=1),
    "AA": st.number_input("Administrative Assistant (£/day)", min_value=0, value=152, step=1),
    "IT": st.number_input("IT Professional (£/day)", min_value=0, value=187, step=1),
    "EC": st.number_input("External Consultant (£/day)", min_value=0, value=800, step=1),
}

# Function to create task assignment UI
def create_task_assignment(tasks, task_prefix):
    task_assignments = {}
    
    for task in tasks:
        task_code = task["code"]
        task_name = task["name"]
        defaults = task.get("defaults", {})
        
        st.subheader(f"{task_code}: {task_name}")
        cols = st.columns(6)
        
        task_assignments[task_code] = {
            "name": task_name,
            "positions": {},
            "company_type_factors": task.get("company_type_factors", {})
        }
        
        for i, position in enumerate(["SO", "LAW", "PM", "AA", "IT", "EC"]):
            with cols[i]:
                # Use default value for this position if available, otherwise use 1.0
                default_value = defaults.get(position, 1.0)
                days = st.number_input(
                    f"{position} days", 
                    min_value=0.0, 
                    value=default_value, 
                    step=0.5,
                    key=f"{task_prefix}_{task_code}_{position}"
                )
                task_assignments[task_code]["positions"][position] = days
    
    return task_assignments

# Initialize task assignments dictionary
task_assignments = {}

# Show appropriate task assignments based on selection
if cost_type == "SET UP COSTS" or cost_type == "BOTH COSTS":
    setup_assignments = create_task_assignment(setup_tasks, "setup")
    task_assignments.update(setup_assignments)

if cost_type == "ON-GOING COSTS" or cost_type == "BOTH COSTS":
    if cost_type == "BOTH COSTS":
        st.header("ON-GOING COSTS - Task Assignment")
    ongoing_assignments = create_task_assignment(ongoing_tasks, "ongoing")
    task_assignments.update(ongoing_assignments)

# Company type selection
st.header("Company Type")
company_type = st.selectbox(
    "Select your company type",
    options=[
        "Upstream operator (non-SME)",
        "Upstream operator (SME)",
        "Downstream operator (non-SME)",
        "Downstream operator (SME)",
        "Trader (non-SME)",
        "Trader (SME)"
    ]
)

# Business size discount (only applicable to SME companies)
business_size_discount = 1.0  # Default for non-SME companies
if "(SME)" in company_type:
    st.header("Business Size Discount")
    business_size = st.selectbox(
        "Select your business size (only applicable to SME companies)",
        options=[
            "Medium",
            "Small",
            "Micro"
        ],
        index=0
    )
    
    # Set default discount factor based on selection
    if business_size == "Small":
        default_business_size_discount = 0.75
    elif business_size == "Micro":
        default_business_size_discount = 0.5
    else:  # Medium
        default_business_size_discount = 1.0
    
    # Add ability to edit the factor
    business_size_discount = st.number_input(
        "Business size discount factor (adjust if needed)",
        min_value=0.0, 
        max_value=5.0, 
        value=default_business_size_discount, 
        step=0.01,
        format="%.2f",
        key="business_size_discount"
    )
else:
    business_size_discount = 1.0  # No discount for non-SME companies

# Adjustment factors section (excluding company type which is now task-specific)
st.header("Other Adjustment Factors")

col1, col2 = st.columns(2)

with col1:
    # Due diligence compliance
    st.subheader("Due Diligence Compliance")
    
    default_dd_compliance_types = {
        "No due diligence": {"setup": 1.00, "ongoing": 1.00},
        "Partial due diligence": {"setup": 0.30, "ongoing": 0.30},
        "Full due diligence": {"setup": 0.75, "ongoing": 0.50},  # Different factors for setup vs ongoing
    }
    
    dd_compliance = st.selectbox("Select compliance level", list(default_dd_compliance_types.keys()))
    default_dd_factors = default_dd_compliance_types[dd_compliance]
    
    # Add ability to edit the factors
    st.write("Due diligence factors (adjust if needed)")
    dd_setup_factor = st.number_input(
        "Setup cost factor",
        min_value=0.0, 
        max_value=5.0, 
        value=default_dd_factors["setup"], 
        step=0.01,
        format="%.2f",
        key="dd_setup_factor"
    )
    dd_ongoing_factor = st.number_input(
        "Ongoing cost factor",
        min_value=0.0, 
        max_value=5.0, 
        value=default_dd_factors["ongoing"], 
        step=0.01,
        format="%.2f",
        key="dd_ongoing_factor"
    )
    
    # Source country
    st.subheader("Risk Level in Source Country")
    
    default_risk_types = {
        "Low risk country": 0.50,
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

# NOW DO ALL CALCULATIONS AFTER ALL INPUTS ARE DEFINED
# Calculate base costs and apply company type factors
base_costs_by_task_position = {}
position_totals = {"SO": 0, "LAW": 0, "PM": 0, "AA": 0, "IT": 0, "EC": 0}
task_totals = {}
task_categories = {}
adjusted_task_totals = {}

for task_code, task_data in task_assignments.items():
    task_name = task_data["name"]
    positions = task_data["positions"]
    company_factors = task_data["company_type_factors"]
    
    base_costs_by_task_position[task_code] = {}
    task_total = 0
    
    # Determine if this is a setup or ongoing task
    is_setup = task_code.startswith("S")
    task_categories[task_code] = "SET UP COSTS" if is_setup else "ON-GOING COSTS"
    
    # Get company type factor for this task
    company_factor = company_factors.get(company_type, 1.0)
    
    for position, days in positions.items():
        cost = days * daily_rates[position]
        base_costs_by_task_position[task_code][position] = cost
        position_totals[position] += cost
        task_total += cost
    
    task_totals[task_code] = task_total
    adjusted_task_totals[task_code] = task_total * company_factor

total_base_cost = sum(task_totals.values())
total_after_company_adjustment = sum(adjusted_task_totals.values())

# Calculate the final adjusted cost sequentially
# First separate setup and ongoing costs from company-adjusted totals
setup_cost_after_company = sum([adjusted_task_totals[code] for code in adjusted_task_totals if code.startswith("S")])
ongoing_cost_after_company = sum([adjusted_task_totals[code] for code in adjusted_task_totals if code.startswith("O")])

# Apply due diligence factors (these are applied after company type adjustments)
adjusted_setup_after_dd = setup_cost_after_company * dd_setup_factor
adjusted_ongoing_after_dd = ongoing_cost_after_company * dd_ongoing_factor
adjusted_cost_after_dd = adjusted_setup_after_dd + adjusted_ongoing_after_dd

# Apply other factors (same for all costs)
adjusted_cost_after_supply_chain = adjusted_cost_after_dd * supply_chain_factor
adjusted_cost_after_commodity = adjusted_cost_after_supply_chain * commodity_factor
adjusted_cost_after_risk = adjusted_cost_after_commodity * risk_factor

# Apply business size discount (only for SME companies)
final_adjusted_cost = adjusted_cost_after_risk * business_size_discount

# Create detailed cost breakdown by task and position
detailed_data = []
for task_code, task_data in task_assignments.items():
    task_name = task_data["name"]
    positions = task_data["positions"]
    company_factor = task_data["company_type_factors"].get(company_type, 1.0)
    
    for position in ["SO", "LAW", "PM", "AA", "IT", "EC"]:
        if position in positions and positions[position] > 0:
            base_cost = positions[position] * daily_rates[position]
            adjusted_cost = base_cost * company_factor
            detailed_data.append({
                "Task Code": task_code,
                "Task": task_name,
                "Position": position,
                "Work Days": positions[position],
                "Daily Rate (£)": daily_rates[position],
                "Base Cost (£)": base_cost,
                "Company Factor": company_factor,
                "Adjusted Cost (£)": adjusted_cost,
                "Category": task_categories[task_code]
            })

detailed_df = pd.DataFrame(detailed_data)

# Create task summary
task_summary = []
for task_code in task_totals:
    if task_totals[task_code] > 0:  # Only include tasks with actual costs
        company_factor = task_assignments[task_code]["company_type_factors"].get(company_type, 1.0)
        task_summary.append({
            "Task Code": task_code,
            "Task": task_assignments[task_code]["name"],
            "Category": task_categories[task_code],
            "Base Cost (£)": task_totals[task_code],
            "Company Factor": company_factor,
            "Adjusted Cost (£)": task_totals[task_code] * company_factor
        })

task_summary_df = pd.DataFrame(task_summary)

# Create position summary (only include positions with costs > 0)
position_summary = []
for position in position_totals:
    if position_totals[position] > 0:
        position_summary.append({
            "Position": position,
            "Total Cost (£)": position_totals[position]
        })

position_summary_df = pd.DataFrame(position_summary)

# Create category summary
if not task_summary_df.empty:
    category_summary = task_summary_df.groupby('Category').agg({
        'Base Cost (£)': 'sum',
        'Adjusted Cost (£)': 'sum'
    }).reset_index()
else:
    category_summary = pd.DataFrame()

# Display results
st.header("Budget Results")

# Display the results
col1, col2 = st.columns(2)

with col1:
    st.subheader("Detailed Cost Breakdown")
    if not detailed_df.empty:
        st.dataframe(detailed_df, use_container_width=True)
    else:
        st.info("No costs to display. Please assign work days to tasks.")
    
    st.subheader("Task Summary")
    if not task_summary_df.empty:
        st.dataframe(task_summary_df, use_container_width=True)
    else:
        st.info("No tasks with assigned costs to display.")
    
    # Show applied factors
    factors_data = [
        {"Factor": "Due Diligence Compliance", "Setup Value": f"{dd_setup_factor:.2f}", "Ongoing Value": f"{dd_ongoing_factor:.2f}", "Description": dd_compliance},
        {"Factor": "Supply Chain Complexity", "Setup Value": f"{supply_chain_factor:.2f}", "Ongoing Value": f"{supply_chain_factor:.2f}", "Description": supply_chain},
        {"Factor": "Commodity Count", "Setup Value": f"{commodity_factor:.2f}", "Ongoing Value": f"{commodity_factor:.2f}", "Description": f"{commodity_count} commodities"},
        {"Factor": "Country Risk Level", "Setup Value": f"{risk_factor:.2f}", "Ongoing Value": f"{risk_factor:.2f}", "Description": risk_type},
        {"Factor": "Business Size Discount", "Setup Value": f"{business_size_discount:.2f}", "Ongoing Value": f"{business_size_discount:.2f}", "Description": "Applied to SME companies only"},
    ]
    factors_df = pd.DataFrame(factors_data)
    st.subheader("Applied Factors")
    st.dataframe(factors_df, use_container_width=True)

with col2:
    # Position summary pie chart
    if not position_summary_df.empty:
        fig1 = px.pie(
            position_summary_df,
            values="Total Cost (£)",
            names="Position",
            title="Base Cost Distribution by Position",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No position costs to display in chart.")
    
    # Task summary bar chart
    if not task_summary_df.empty:
        fig2 = px.bar(
            task_summary_df,
            x="Task Code",
            y="Adjusted Cost (£)",
            title="Adjusted Cost Distribution by Task",
            hover_data=["Task", "Base Cost (£)", "Company Factor"],
            color="Category",
            color_discrete_map={"SET UP COSTS": "#1f77b4", "ON-GOING COSTS": "#ff7f0e"},
            category_orders={"Category": ["SET UP COSTS", "ON-GOING COSTS"]}
        )
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No task costs to display in chart.")
    
    # Category pie chart
    if not category_summary.empty:
        fig3 = px.pie(
            category_summary,
            values="Adjusted Cost (£)",
            names="Category",
            title="Adjusted Cost Distribution by Category",
            color="Category",
            color_discrete_map={"SET UP COSTS": "#1f77b4", "ON-GOING COSTS": "#ff7f0e"},
            hover_data=["Base Cost (£)"]
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No category costs to display in chart.")

# Show total costs in a more organized way
st.header("Cost Summary")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Base Cost (Before Adjustments)", f"£{total_base_cost:,.2f}")
with col2:
    st.metric("After Company Type Adjustment", f"£{total_after_company_adjustment:,.2f}", 
              delta=f"{((total_after_company_adjustment/total_base_cost)-1)*100:.1f}%" if total_base_cost > 0 else "0%")
with col3:
    st.metric(
        "Final Adjusted Cost", 
        f"£{final_adjusted_cost:,.2f}", 
        delta=f"{((final_adjusted_cost/total_after_company_adjustment)-1)*100:.1f}%" if total_after_company_adjustment > 0 else "0%"
    )

# Detailed breakdown
st.header("Detailed Calculation Breakdown")
with st.expander("View detailed calculation breakdown"):
    st.markdown(f"""
    ### Base Cost
    - **Total Base Cost**: £{total_base_cost:,.2f}
    - **Setup Costs**: £{setup_cost_after_company :,.2f}
    - **Ongoing Costs**: £{ongoing_cost_after_company:,.2f}
    
    ### Company Type Adjustment (per task)
    - **After Company Type Adjustment**: £{total_after_company_adjustment:,.2f}
    
    ### Sequential Factor Application
    1. **Due Diligence Compliance Adjustment** ({dd_compliance}):
       - Setup: £{setup_cost_after_company:,.2f} × {dd_setup_factor:.2f} = £{adjusted_setup_after_dd:,.2f}
       - Ongoing: £{ongoing_cost_after_company:,.2f} × {dd_ongoing_factor:.2f} = £{adjusted_ongoing_after_dd:,.2f}
       - **Subtotal**: £{adjusted_cost_after_dd:,.2f}
    2. **Supply Chain Complexity Adjustment** ({supply_chain}): £{adjusted_cost_after_dd:,.2f} × {supply_chain_factor:.2f} = £{adjusted_cost_after_supply_chain:,.2f}
    3. **Commodities Adjustment** ({commodity_count}): £{adjusted_cost_after_supply_chain:,.2f} × {commodity_factor:.2f} = £{adjusted_cost_after_commodity:,.2f}
    4. **Country Risk Adjustment** ({risk_type}): £{adjusted_cost_after_commodity:,.2f} × {risk_factor:.2f} = £{adjusted_cost_after_risk:,.2f}
    5. **Business Size Discount**: £{adjusted_cost_after_risk:,.2f} × {business_size_discount:.2f} = £{final_adjusted_cost:,.2f}
    
    ### Final Adjusted Cost: £{final_adjusted_cost:,.2f}
    """)

# Add section to download results
st.header("Download Results")

# Prepare data for download
def create_download_data():
    # Create a dictionary of DataFrames
    data = {
        "Summary": pd.DataFrame([
            {"Information": "Calculation Date", "Value": f"{pd.Timestamp.now().strftime('%Y-%m-%d')}"},
            {"Information": "Cost Type", "Value": cost_type},
            {"Information": "Company Type", "Value": company_type},
            {"Information": "Business Size Discount", "Value": f"{business_size_discount:.2f}" if "SME" in company_type else "N/A (non-SME)"},
            {"Information": "Total Base Cost (Before Adjustments)", "Value": f"£{total_base_cost:,.2f}"},
            {"Information": "Final Adjusted Cost", "Value": f"£{final_adjusted_cost:,.2f}"}
        ]),
        "Applied_Factors": pd.DataFrame(factors_data),
        "Calculation_Steps": pd.DataFrame([
            {"Step": "Base Cost", "Value": f"£{total_base_cost:,.2f}"},
            {"Step": "After Company Type Adjustment", "Value": f"£{total_after_company_adjustment:,.2f}"},
            {"Step": f"Due Diligence Compliance Adjustment ({dd_compliance})", "Value": f"£{adjusted_cost_after_dd:,.2f}"},
            {"Step": f"Supply Chain Complexity Adjustment ({supply_chain})", "Value": f"£{adjusted_cost_after_supply_chain:,.2f}"},
            {"Step": f"Commodities Adjustment ({commodity_count})", "Value": f"£{adjusted_cost_after_commodity:,.2f}"},
            {"Step": f"Country Risk Adjustment ({risk_type})", "Value": f"£{adjusted_cost_after_risk:,.2f}"},
            {"Step": "Business Size Discount", "Value": f"£{final_adjusted_cost:,.2f}"}
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