import requests
import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint

# Initialize rich console
console = Console()

def format_datetime(date_string):
    """Helper function to parse and format ISO date strings from CoinGecko."""
    if not date_string:
        return "N/A"
    try:
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        dt_object = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return dt_object.strftime("%B %d, %Y at %I:%M:%S %p %Z")
    except ValueError as ve:
        rprint(f"[yellow]Warning:[/yellow] Could not parse date: {date_string}. Error: {ve}")
        return date_string
    except Exception as e:
        rprint(f"[yellow]Warning:[/yellow] Error formatting date '{date_string}': {e}")
        return "Error formatting date"

def get_token_data(contract_address):
    """Fetches token data from CoinGecko API."""
    url = f"https://api.coingecko.com/api/v3/coins/solana/contract/{contract_address}"
    headers = {'accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        name = data.get('name', 'N/A')
        symbol = data.get('symbol', 'N/A')
        genesis_date_str = data.get('genesis_date')
        coin_id = data.get('id')  # Get CoinGecko ID for historical price query
        market_data = data.get('market_data', {})
        ath_data = market_data.get('ath', {})
        ath_date_data = market_data.get('ath_date', {})

        ath_usd = ath_data.get('usd')
        ath_date_str = ath_date_data.get('usd')

        formatted_ath_date = format_datetime(ath_date_str)
        formatted_genesis_date = format_datetime(genesis_date_str)

        if ath_usd is None:
            rprint(f"[bold yellow]Warning:[/bold yellow] ATH price data not found for {name} ({symbol}).")
            return None

        return {
            "name": name,
            "symbol": symbol.upper() if symbol else 'N/A',
            "ath_usd": ath_usd,
            "ath_date": formatted_ath_date,
            "genesis_date": formatted_genesis_date,
            "contract_address": contract_address,
            "coin_id": coin_id  # Include coin_id for historical price
        }

    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 404:
            rprint(f"[bold red]Error:[/bold red] Coin not found on CoinGecko (404). Please check the contract address: [cyan]{contract_address}[/cyan]")
        else:
            rprint(f"[bold red]HTTP Error:[/bold red] {http_err} - {response.text}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        rprint(f"[bold red]Network Error:[/bold red] Could not connect to CoinGecko. {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        rprint(f"[bold red]Error:[/bold red] Request timed out connecting to CoinGecko. {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        rprint(f"[bold red]Error:[/bold red] An error occurred during the request: {req_err}")
        return None
    except Exception as e:
        rprint(f"[bold red]An unexpected error occurred:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        return None

def get_historical_price(coin_id, date_str):
    """Fetches historical price data for a specific date from CoinGecko."""
    # Format date to CoinGecko's required format: dd-mm-yyyy
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        formatted_date = dt.strftime("%d-%m-%Y")
    except ValueError as ve:
        rprint(f"[bold red]Error:[/bold red] Invalid date format: {date_str}. Please use YYYY-MM-DD HH:MM:SS format.")
        return None

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history?date={formatted_date}"
    headers = {'accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        market_data = data.get('market_data', {})
        current_price = market_data.get('current_price', {})
        price_usd = current_price.get('usd')

        if price_usd is None:
            rprint(f"[bold yellow]Warning:[/bold yellow] No price data available for {coin_id} on {formatted_date}.")
            return None

        return price_usd

    except requests.exceptions.HTTPError as http_err:
        rprint(f"[bold red]HTTP Error:[/bold red] {http_err} - {response.text}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        rprint(f"[bold red]Network Error:[/bold red] Could not connect to CoinGecko. {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        rprint(f"[bold red]Error:[/bold red] Request timed out connecting to CoinGecko. {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        rprint(f"[bold red]Error:[/bold red] An error occurred during the request: {req_err}")
        return None
    except Exception as e:
        rprint(f"[bold red]An unexpected error occurred:[/bold red] {e}")
        return None

def calculate_return_percentage(ath_price, historical_price):
    """Calculates the return percentage from historical price to ATH."""
    if historical_price == 0:
        rprint("[bold red]Error:[/bold red] Historical price is zero, cannot calculate return.")
        return None
    return ((ath_price / historical_price) - 1) * 100

def display_results(token_data, historical_price=None, return_percentage=None, input_date=None):
    """Displays the fetched token data and historical price info in a rich Panel."""
    if not token_data:
        rprint("[bold red]Failed to retrieve token data.[/bold red] Cannot display results.")
        return

    console.rule("[bold blue]Results[/bold blue]")

    ath_price_str = f"${token_data['ath_usd']:.8f}" if token_data.get('ath_usd') is not None else "[yellow]N/A[/yellow]"

    content = (
        f"[bold]Name:[/bold] {token_data.get('name', 'N/A')}\n"
        f"[bold]Symbol:[/bold] {token_data.get('symbol', 'N/A')}\n"
        f"[bold]Contract Address:[/bold] [cyan]{token_data.get('contract_address', 'N/A')}[/cyan]\n"
        f"--------------------\n"
        f"[bold]ATH Price (USD):[/bold] [green]{ath_price_str}[/green]\n"
        f"[bold]ATH Date:[/bold] {token_data.get('ath_date', 'N/A')}\n"
        f"--------------------\n"
        f"[bold]CoinGecko Listing Date:[/bold] {token_data.get('genesis_date', 'N/A')} [italic](Note: Not blockchain creation date)[/italic]"
    )

    if historical_price is not None and input_date:
        content += (
            f"\n--------------------\n"
            f"[bold]Historical Price (USD) on {input_date}:[/bold] [green]${historical_price:.8f}[/green]"
        )
        if return_percentage is not None:
            content += (
                f"\n[bold]Return from {input_date} to ATH:[/bold] [green]{return_percentage:.2f}%[/green]"
            )

    panel = Panel(
        content,
        title=f"Token Information: {token_data.get('name', 'Unknown Token')}",
        subtitle=f"Data from CoinGecko",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(panel)

if __name__ == "__main__":
    console.rule("[bold magenta]Solana Token ATH Checker[/bold magenta]")

    contract_address = Prompt.ask("[bold]Enter the Solana Contract Address[/bold]")

    if not contract_address or len(contract_address) < 32 or len(contract_address) > 45:
        rprint("[bold red]Error:[/bold red] Invalid contract address format entered.")
        sys.exit(1)

    contract_address = contract_address.strip().lower()

    console.print(f"\n[grey50]Fetching data for address:[/grey50] [cyan]{contract_address}[/cyan]")

    with console.status("[bold green]Calling CoinGecko API...", spinner="dots"):
        token_data = get_token_data(contract_address)

    if token_data:
        display_results(token_data)

        # Ask for historical date
        date_input = Prompt.ask(
            "[bold]Enter a date and time to check historical price (YYYY-MM-DD HH:MM:SS)[/bold]",
            default="2023-01-01 00:00:00"
        )

        try:
            # Validate date format
            datetime.fromisoformat(date_input.replace(' ', 'T'))
            with console.status("[bold green]Fetching historical price...", spinner="dots"):
                historical_price = get_historical_price(token_data['coin_id'], date_input)

            if historical_price is not None:
                return_percentage = calculate_return_percentage(token_data['ath_usd'], historical_price)
                display_results(
                    token_data,
                    historical_price=historical_price,
                    return_percentage=return_percentage,
                    input_date=date_input
                )
            else:
                rprint("[yellow]Could not fetch historical price data.[/yellow]")

        except ValueError:
            rprint("[bold red]Error:[/bold red] Invalid date format. Please use YYYY-MM-DD HH:MM:SS.")
    else:
        rprint("\n[yellow]Could not display results due to errors during data fetching.[/yellow]")

    console.print("\n[grey50]Script finished.[/grey50]")