# data cleaning
import pandas as pd
import numpy as np
# webscraping
from bs4 import BeautifulSoup
import requests
# text parsing
import re


def get_sic_codes():
    """
    Scrape the SIC (Industry) Codes from SEC's
    EDGAR website and return a dataframe with
    the mapping between SIC Code, granular-level
    industry, and higher-level industry information
    """
    # Scraping SIC Code (Industry) Data
    url = "https://www.sec.gov/info/edgar/siccodes.htm"
    res = requests.get(url)
    soup = BeautifulSoup(res.text,"lxml")
    data = []
    for tr in soup.find(class_="sic").find_all("tr"):
        data.append([item.get_text(strip=True) for item in tr.find_all(["th","td"])])
    # SIC Code data cleaning
    sic_codes = pd.DataFrame(data[1:])
    sic_codes.columns = data[0]
    sic_codes.Office = sic_codes.Office.apply(lambda x: x.replace("Office of", ""))
    sic_codes = sic_codes.astype({'SIC Code': int})
    return sic_codes

def load_company_data(year=2019, quarter='Q2'):
    """
    Loading submissions downloaded from the EDGAR website
    and filtering for Quarterly Financial Submissions
    (10-Q) based on inputted year (default = 2019)
    and quarter (default = Q2). Returns a dataframe
    with company name, submission unique id (adsh), 
    and filing details (form, fiscal year, period, etc.)
    """
    # pulling in company submission data
    sub = pd.read_csv('data/sub.txt', header = 0, sep='\t')
    # filtering EDGAR submissions on quarterly financial statements
    sub_10Q = sub[sub['form']=='10-Q']
    sub_columns = ['adsh', 'name', 'sic', 'countryba', 'form', 'fye', 'period', 'fy', 'fp', 'detail', 'instance']
    # choosing submissions as of Q2 2019
    sub_10Q_cols = sub_10Q.loc[(sub_10Q['fy'] == year) & (sub_10Q['fp'] == quarter), sub_columns]
    sub_10Q_cols_filtered = sub_10Q_cols.loc[:, sub_columns].sort_values(by='name')
    print(f"Number of Companies: {len(sub_10Q_cols_filtered)}")
    sub_10Q_cols_filtered_dups_removed = sub_10Q_cols_filtered.\
                                                                groupby('name').\
                                                                filter(lambda x: len(x) >= 1).\
                                                                drop_duplicates('name')
    print(f"After Duplicates were Removed: {len(sub_10Q_cols_filtered_dups_removed)}")
    return sub_10Q_cols_filtered_dups_removed


def load_company_financials(df, sic_df, tags):
    """
    Loading financials line items from the EDGAR website
    and joining with supplied company/submission dataframe
    and sic industry codes. (Note: df should have 'adsh'
    field to uniquely identify submission of interest)
    Requires user to also supply names of the financial
    submission line items (tags) to be retained.
    Finally, transforms long dataset to wide dataset.
    """
    # pulling in company financial data
    num = pd.read_csv("data/num.txt", sep = "\t", header=0)
    
    # merging with company data to identify appropriate submissions
    company_num = df.merge(num, how='left', on='adsh')
    company_num = company_num.astype({'sic': int})
    
    # filtering on necessary tags, reporting period, etc.
    company_num_filtered = company_num[(company_num['tag'].isin(tags)) & \
                                            (company_num['ddate']==company_num['period']) & \
                                            (company_num['qtrs'].isin([0, 1, 2])) & \
                                            (company_num['coreg'].isna()) & \
                                            (company_num['value'].isna() != True) & \
                                            (company_num['uom'] == 'USD')]
    company_num_filtered.sort_values(by=['name', 'tag', 'qtrs'], axis=0, inplace=True)
    first_values = company_num_filtered.drop(columns=['qtrs', 'value', 'footnote']).drop_duplicates(inplace=False)
    company_num_filtered_no_dups = company_num_filtered.loc[first_values.index]
    df = company_num_filtered_no_dups.pivot(index = 'name', columns = 'tag', values = "value")
    
#     # merging with sic dataframe
#     company_num_sic = company_num_filtered_no_dups.merge(sic_df, how='left', left_on='sic', right_on='SIC Code')
#     company_num_sic.drop('SIC Code', axis=1, inplace=True)
    
    print(f"Final number of companies: {len(df)}")
    return df

def define_tags_by_type():
    """ 
    Returns "tags" (names of financial statement
    line items references in the numerical dataset)
    by category. Note that this is necessary as 
    not all line items have the same name across
    different companies. 
    This function returns (16) different lists in 
    the following order (with the items in the list
    ordered by 10-Q popularity across companies):
    1. All tags necessary (to select dataset rows)
    2. Revenue
    3. Net Income
    4. Fixed Assets (or, Non-Current Assets portion)
    5. Current Assets
    6. Current Liabilities
    7. Long-term Debt
    8. Cost of Goods Sold (COGS)
    9. Inventory
    10. Accounts Receivable
    11. Cash
    12. Marketable Securities
    13. Accounts Payable
    14. Short-term Debt
    15. Accrued Liabilities
    16. Assets, Liabilities, and Equity
    """
    revenue = ['Revenues',
                 'RevenueFromContractWithCustomerExcludingAssessedTax',
                 'RevenueFromContractWithCustomerIncludingAssessedTax',
                 'RevenueRemainingPerformanceObligation',
                 'RevenueFromRelatedParties','RevenuesNetOfInterestExpense',
                 'RevenueNotFromContractWithCustomer']

    net_income = ['NetIncomeLoss', 'ProfitLoss']
    fixed_asset = ['AssetsNoncurrent']
    current_asset = ['AssetsCurrent','AssetsCurrentExcludingRestrictedCash',
                     'AssetsCurrentFairValueDisclosure', 'AssetsCurrentOther']
    current_liabilities = ['LiabilitiesCurrent',
                             'AccruedLiabilitiesCurrent',
                             'EmployeeRelatedLiabilitiesCurrent',
                             'OtherAccruedLiabilitiesCurrent',
                             'OtherLiabilitiesCurrent',
                             'AccountsPayableAndAccruedLiabilitiesCurrent',
                             'AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent']
    lt_debt = ['LongTermDebtNoncurrent','LongTermDebt',
               'DebtInstrumentCarryingAmount', 'DebtLongtermAndShorttermCombinedAmount']
    cogs = ['CostOfGoodsAndServicesSold', 'CostOfSales']
    inventory = ['InventoryNet','InventoryGross','InventoryFinishedGoods',
                 'InventoryWorkInProcessNetOfReserves','InventoryRawMaterialsNetOfReserves',
                 'InventoryWorkInProcess','InventoryRawMaterials']
    receivables = ['AccountsReceivableNetCurrent',
                    'AccountsReceivableNet','ReceivablesNetCurrent']
    cash = ['CashAndCashEquivalentsAtCarryingValue',
             'NetCashProvidedByUsedInOperatingActivities',
             'NetCashProvidedByUsedInFinancingActivities',
             'NetCashProvidedByUsedInInvestingActivities',
             'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents']
    marketable_sec = ['MarketableSecurities', 'MarketableSecuritiesCurrent',
                      'MarketableSecuritiesNoncurrent', 'MarketableSecuritiesNoncurrent']
    accounts_payable = ['AccountsPayableCurrent', 'AccountsPayableAndAccruedLiabilitiesCurrent']
    st_debt = ['ShortTermBorrowings', 'ProceedsFromRepaymentsOfShortTermDebt',
               'LongTermDebtCurrent']
    accured_liabilities = ['AccruedLiabilitiesCurrent','OtherAccruedLiabilitiesCurrent',
                             'AccountsPayableAndAccruedLiabilitiesCurrent',
                             'AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent',
                             'AccruedLiabilitiesAndOtherLiabilities']
    asset_liabilities = ['Assets', 'LiabilitiesAndStockholdersEquity','LiabilitiesNoncurrent',
                         'Liabilities', 'StockholdersEquity',]
    all_tags = list(set(revenue + net_income + fixed_asset + current_asset + current_asset + current_liabilities +\
                lt_debt + cogs + inventory + receivables + cash + marketable_sec + accounts_payable +\
                st_debt + accured_liabilities + asset_liabilities))
    
    return all_tags, revenue, net_income, fixed_asset, current_asset, current_liabilities,\
            lt_debt, cogs, inventory, receivables, cash, marketable_sec, accounts_payable,\
            st_debt, accured_liabilities, asset_liabilities


def fill_in_value_priority(df, tag_list, new_col_name):
    df[new_col_name] = 0
    for k in tag_list:
        df[new_col_name] = df.apply(lambda x: x[k] if x[new_col_name] == 0 else x[new_col_name], axis=1)
    df[new_col_name] = df[new_col_name].fillna(0)
    return df

def calc_ROE(df):
    df['ROE_'] = df['NetIncome_'].div(df['Equity_'])
    df = divide_by_zero_fix(df, 'ROE_', default_value=0)
    return df

def calc_ROA(df):
    df['ROA_'] = df['NetIncome_'].div(df['Assets_'])
    df = divide_by_zero_fix(df, 'ROA_', default_value=0)
    return df

def calc_profit_margin(df):
    df['ProfitMargin_'] = df['NetIncome_'].div(df['Revenue_'])
    df = divide_by_zero_fix(df, 'ProfitMargin_', default_value=0)
    return df

def calc_equity_multiplier(df):
    df['EquityMultiplier_'] = df['Assets_'].div(df['Equity_'])
    df = divide_by_zero_fix(df, 'EquityMultiplier_', default_value=0)
    return df


def calc_fixed_assets_to_net_worth(df):
    df['FixedAssetsToNetWorth_'] = (df['Assets_'] - df['CurrentAssets_']) / df['Equity_']
    df = divide_by_zero_fix(df, 'FixedAssetsToNetWorth_', default_value=0)
    return df

def calc_debt_to_net_worth(df):
    df['DebtToNetWorth_'] = (df['LTDebt_'] + df['STDebt_']) / df['Equity_']
    df = divide_by_zero_fix(df, 'DebtToNetWorth_', default_value=0)
    return df

def calc_asset_turnover(df):
    df['AssetTurnover_'] = df['Revenue_'].div(df['Assets_'])
    df = divide_by_zero_fix(df, 'AssetTurnover_', default_value=0)
    return df

def calc_inventory_turnover(df):
    df['InventoryTurnover_'] = df['COGS_'].div(df['Inventory_'])
    df = divide_by_zero_fix(df, 'InventoryTurnover_', default_value=0)
    return df

def calc_days_receivables(df):
    df['DaysReceivables_'] = 365/(df['Revenue_'].div(df['AccountsReceivable_']))
    df = divide_by_zero_fix(df, 'DaysReceivables_', default_value=0)
    return df

def calc_quick_ratio(df):
    df['QRnumerator_'] = df.apply(lambda x: x.Cash_ + x.MarketableSec_ + x.AccountsReceivable_,
                                       axis=1)
    df['QRdenomerator_'] = df.apply(lambda x: x.STDebt_ + x.AccountsPayable_ + x.AccruedLiabilities_,
                                       axis=1)
    df['QuickRatio_'] = 365/(df['QRnumerator_'].div(df['QRdenomerator_']))
    df = divide_by_zero_fix(df, 'QuickRatio_', default_value=0)
    return df

def divide_by_zero_fix(df, col_name, default_value=0):
    df.loc[~np.isfinite(df[col_name]), col_name] = default_value
    return df

def calc_ratios(df, new_col_names):
    df['Assets_'] = df['Assets'].map(lambda x: 0 if x != x else x)
    df['Liabilities_'] = df.apply(lambda x: x.Liabilities if x.Liabilities == x.Liabilities else\
                                            x.LiabilitiesAndStockholdersEquity - x.StockholdersEquity,
                                            axis=1)
    df['Liabilities_'] = df.apply(lambda x: x.Liabilities_ if x.Liabilities_ == x.Liabilities_ else\
                                            0 if (x.LiabilitiesAndStockholdersEquity - x.Assets_) == 0 else\
                                            x.Liabilities_,
                                            axis=1)
    df.dropna(subset=['Liabilities_'], axis=0, inplace=True)
    df['Equity_'] = df.apply(lambda x: x.StockholdersEquity if x.StockholdersEquity == x.StockholdersEquity else\
                                       x.Assets_ - x.Liabilities_,
                                       axis=1)
    df = df.fillna(value=0)
#     new_col_names = [('NetIncome_', net_income_tags),
#                      ('Revenue_', revenue_tags),
#                      ('CurrentAssets_', current_asset_tags),
#                      ('CurrentLiabilities_', current_liabilities_tags),
#                      ('LTDebt_', lt_debt_tags),
#                      ('STDebt_', st_debt_tags),
#                      ('COGS_', cogs_tags),
#                      ('Inventory_', inventory_tags),
#                      ('Cash_', cash_tags),
#                      ('AccountsReceivable_', receivables_tags),
#                      ('MarketableSec_', marketable_sec_tags),
#                      ('AccountsPayable_', accounts_payable_tags),
#                      ('AccruedLiabilities_', accured_liabilities_tags),
#                      ('FixedAssets_', fixed_asset_tags)]
    for item in new_col_names:
        df = fill_in_value_priority(df, item[1], item[0])
    df = calc_ROE(df)
    df = calc_ROA(df)
    df = calc_profit_margin(df)
    df = calc_equity_multiplier(df)
    df = calc_fixed_assets_to_net_worth(df)
    df = calc_debt_to_net_worth(df)
    df = calc_asset_turnover(df)
    df = calc_inventory_turnover(df)
    df = calc_days_receivables(df)
    df = calc_quick_ratio(df)
    return df

def log_features(df):
    cols_to_look_at = ['Assets_', 'Liabilities_', 'Equity_', 'ROE_', 'ROA_', 'ProfitMargin_',
                                'EquityMultiplier_', 'FixedAssetsToNetWorth_', 'DebtToNetWorth_',
                                'AssetTurnover_', 'InventoryTurnover_', 'DaysReceivables_', 'QuickRatio_']
    df_new = df[cols_to_look_at].copy(deep=True)
    c = 0.01
    for col in cols_to_look_at:
        df_new.loc[col] = df_new[col].apply(lambda x: np.log(c + x))
    return df_new.fillna(0)