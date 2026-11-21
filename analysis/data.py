"""Load and clean the Northwind workbook; define shared time windows."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "Northwind Database.xlsx"

# Matched comparison windows. Each is [start, end): the data covers
# 1996-07-04 to 1998-05-06, so Jan-Apr is the only stretch observed in
# both 1997 and 1998.
PRIOR_WINDOW = (pd.Timestamp("1997-01-01"), pd.Timestamp("1997-05-01"))
CURRENT_WINDOW = (pd.Timestamp("1998-01-01"), pd.Timestamp("1998-05-01"))
# Last twelve complete months, used for "current annual volume".
TTM_WINDOW = (pd.Timestamp("1997-05-01"), pd.Timestamp("1998-05-01"))

# Columns left in the Product sheet by an earlier assignment; not part of
# the Northwind schema.
LEFTOVER_PRODUCT_COLUMNS = ["Cheap", "NewPrice", "Cheap.1", "IsCheap", "Unnamed: 14", "NewPrice.1"]


@dataclass
class Northwind:
    """Cleaned Northwind tables shared by every analysis module.

    Each attribute is also a constructor argument of the same name.

    Attributes:
        orders (pandas.DataFrame): One row per order, with customer
            name and country, shipper name, ``OrderValue``,
            ``Shipped``, ``DaysToShip`` and ``Late``.
        lines (pandas.DataFrame): One row per order line, with
            ``GrossSales``, ``DiscountAmount``, ``Revenue`` and the
            order, customer, product, category and supplier fields.
        products (pandas.DataFrame): Product sheet without leftover
            columns, plus category and supplier names.
        customers (pandas.DataFrame): Customers sheet, company name
            renamed to ``CustomerName``.
        suppliers (pandas.DataFrame): Suppliers sheet, with
            ``SupplierName`` and ``SupplierCountry``.
        employees (pandas.DataFrame): Employees sheet plus
            ``EmployeeName``.
        shippers (pandas.DataFrame): ``ShipperID`` and ``ShipperName``.
        categories (pandas.DataFrame): ``CategoryID`` and
            ``CategoryName``.
    """

    orders: pd.DataFrame
    lines: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    suppliers: pd.DataFrame
    employees: pd.DataFrame
    shippers: pd.DataFrame
    categories: pd.DataFrame

    @property
    def as_of(self):
        """Return the date of the most recent order.

        Args:
            None.

        Returns:
            pandas.Timestamp: Latest ``OrderDate``; used as "today".
        """
        return self.orders["OrderDate"].max()


def load_raw(path=DATA_PATH):
    """Read every sheet of the Northwind workbook.

    Args:
        path (str | pathlib.Path): Excel workbook; defaults to the copy
            in ``data/``.

    Returns:
        dict[str, pandas.DataFrame]: Sheet name to raw sheet contents.
    """
    return pd.read_excel(path, sheet_name=None)


def in_window(dates, window):
    """Flag dates that fall inside a half-open time window.

    Args:
        dates (pandas.Series): Datetime values to test.
        window (tuple[pandas.Timestamp, pandas.Timestamp]): ``(start,
            end)``; start is included, end is excluded.

    Returns:
        pandas.Series: Boolean mask aligned with ``dates``.
    """
    start, end = window
    return (dates >= start) & (dates < end)


def prepare(raw):
    """Clean the raw sheets and join them into analysis tables.

    Drops the leftover Product columns, rounds discounts to 2 decimals,
    sets line revenue to ``UnitPrice * Quantity * (1 - Discount)``, and
    adds order value, days to ship and lateness to each order.
    Unshipped orders get NaN ``DaysToShip`` and ``Late`` False.

    Args:
        raw (dict[str, pandas.DataFrame]): Sheets as returned by
            :func:`load_raw`.

    Returns:
        Northwind: Cleaned, joined tables.
    """
    categories = raw["Categories"][["CategoryID", "CategoryName"]].copy()
    shippers = raw["Shippers"].rename(columns={"CompanyName": "ShipperName"})[["ShipperID", "ShipperName"]]
    suppliers = raw["Suppliers"].rename(columns={"CompanyName": "SupplierName", "Country": "SupplierCountry"})
    customers = raw["Customers"].rename(columns={"CompanyName": "CustomerName"})
    employees = raw["Employees"].copy()
    employees["EmployeeName"] = employees["FirstName"] + " " + employees["LastName"]

    products = raw["Product"].drop(columns=LEFTOVER_PRODUCT_COLUMNS, errors="ignore")
    products = products.merge(categories, on="CategoryID", how="left")
    products = products.merge(suppliers[["SupplierID", "SupplierName", "SupplierCountry"]], on="SupplierID", how="left")

    lines = raw["Orders Details"].copy()
    # Discounts are stored as float32-style values such as 0.0500000007.
    lines["Discount"] = lines["Discount"].round(2)
    lines["GrossSales"] = lines["UnitPrice"] * lines["Quantity"]
    lines["DiscountAmount"] = lines["GrossSales"] * lines["Discount"]
    lines["Revenue"] = lines["GrossSales"] - lines["DiscountAmount"]

    orders = raw["Orders"].copy()
    orders = orders.merge(customers[["CustomerID", "CustomerName", "Country"]], on="CustomerID", how="left")
    orders = orders.rename(columns={"Country": "CustomerCountry"})
    orders = orders.merge(shippers, left_on="ShipVia", right_on="ShipperID", how="left")
    order_value = lines.groupby("OrderID")["Revenue"].sum().rename("OrderValue")
    orders = orders.merge(order_value, on="OrderID", how="left")
    orders["Shipped"] = orders["ShippedDate"].notna()
    orders["DaysToShip"] = (orders["ShippedDate"] - orders["OrderDate"]).dt.days
    orders["Late"] = orders["Shipped"] & (orders["ShippedDate"] > orders["RequiredDate"])

    lines = lines.merge(
        orders[["OrderID", "OrderDate", "CustomerID", "CustomerName", "CustomerCountry", "EmployeeID", "ShipVia"]],
        on="OrderID",
        how="left",
    )
    lines = lines.merge(
        products[["ProductID", "ProductName", "CategoryName", "SupplierID", "SupplierName", "Discontinued"]],
        on="ProductID",
        how="left",
    )

    return Northwind(
        orders=orders,
        lines=lines,
        products=products,
        customers=customers,
        suppliers=suppliers,
        employees=employees,
        shippers=shippers,
        categories=categories,
    )


def load(path=DATA_PATH):
    """Load the workbook and return the cleaned tables.

    Args:
        path (str | pathlib.Path): Excel workbook; defaults to the copy
            in ``data/``.

    Returns:
        Northwind: Cleaned, joined tables.
    """
    return prepare(load_raw(path))
