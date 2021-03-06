from typing import List, Dict, Tuple
from itertools import product
from random import choice, random
import re
from enum import Enum
from .database import DB

NEW_PLAYER_MONEY = 500

# NOTE: ALL set_money must be done after get_money, since the stored field values may be outdated by other sessions


class GameMessage:
    """used to share information with bot, tells bot how to respond (i.e. reject/finish/etc.)"""
    BOT_SEND = "BOT SEND"
    BOT_PAUSE = "BOT PAUSE"
    BOT_REJECT = "BOT REJECT"
    BOT_FINISH = "BOT FINISH"

    def __init__(self, bot_response_action, response):
        self.bot_action, self.response = bot_response_action, response


class Blackjack:
    card_suit = ['红桃', '黑桃', '方块', '梅花']
    card_rank = list(range(2, 11)) + ['J', 'Q', 'K', 'A']
    cards: List[str] = list(map(lambda t: str(t[0]) + str(t[1]), product(card_suit, card_rank)))

    player_hand: List[str] = []  # cards in player's hand
    dealer_hand: List[str] = []

    class GamePhase(Enum):
        """describing the game phase/state"""
        PLAYER_ACTION = 1
        INSURANCE = 2

    game_phase: GamePhase = None  # used to validate player actions etc.

    # this defines the available actions for the player at each game phase
    PHASE_ACTIONS: Dict[GamePhase, List[str]] = {
        GamePhase.INSURANCE: ['是', '否'],
        GamePhase.PLAYER_ACTION: ['要牌', '双倍', '停牌']
    }

    def __init__(self, bet: int, player_qq: str, dealer_qq: str):
        """:param bet: the amount of bet for this game"""
        self.bet, self.player_qq, self.dealer_qq = bet, player_qq, dealer_qq

        self.card_suit = ['红桃', '黑桃', '方块', '梅花']
        self.card_rank = list(range(2, 11)) + ['J', 'Q', 'K', 'A']
        self.cards: List[str] = list(map(lambda t: str(t[0]) + str(t[1]), product(self.card_suit, self.card_rank)))
        self.player_hand, self.dealer_hand = [], []

        self.total_money_player = DB.get_money(self.player_qq)
        self.total_money_dealer = DB.get_money(self.dealer_qq)
        if self.total_money_player is None:
            # no record for player_qq
            DB.insert_new(self.player_qq, NEW_PLAYER_MONEY)
            self.total_money_player = NEW_PLAYER_MONEY
        if self.total_money_dealer is None:
            # no record for dealer_qq
            DB.insert_new(self.dealer_qq, NEW_PLAYER_MONEY)
            self.total_money_dealer = NEW_PLAYER_MONEY
        print('player money b4', self.total_money_player, 'dealer money b4', self.total_money_dealer)

    @staticmethod
    def _cards_sum(cards: List) -> int:
        """calculates sum of cards under blackjack rules"""

        def get_ranks_list(card_list: List) -> List[str]:
            """extract a list of ranks (i.e. [10, Q]) from cards list (i.e. "梅花10", "黑桃Q")"""
            pattern = re.compile('..(\d+|[JQKA])')
            return list(map(lambda card: pattern.findall(card)[0], card_list))

        def to_number(rank) -> int:
            if rank in ['J', 'Q', 'K']:
                return 10
            elif rank == 'A':
                # returns 11 always, functions that use this may change 11 to 1 as per rules
                return 11
            else:
                rank = int(rank)
                return rank

        ranks_list = get_ranks_list(cards)
        rank_numbers = list(map(to_number, ranks_list))
        curr_sum = sum(rank_numbers)
        if curr_sum > 21:
            # change 11 to 1, if present
            for i in range(len(rank_numbers)):
                if rank_numbers[i] == 11:
                    rank_numbers[i] = 1
                    new_sum = sum(rank_numbers)
                    if new_sum <= 21:
                        # okay, no need to check for more A cards
                        return new_sum
                    # else check for more A cards
            return sum(rank_numbers)
        else:  # curr_sum <= 21
            return curr_sum

    @staticmethod
    def comma_concat(str_list: List[str]):
        return '，'.join(str_list)

    def game_start(self) -> GameMessage:
        """
        game start, deal cards, returns Chinese string describing game state and possible actions
        NOTE: DO NOT USE BOT_REJECT IN HERE, THIS SHOULD ONLY BE RUN ONCE, MAIN GAME LOOP IS RIGHT AFTER THIS
        """
        print("game_start, length of cards is", len(self.cards))

        # draw initial cards
        dealer_card1 = choice(self.cards)
        self.cards.remove(dealer_card1)
        dealer_card2 = choice(self.cards)
        self.cards.remove(dealer_card2)
        # dealer_card1 should not be visible to player
        self.dealer_hand.extend([dealer_card1, dealer_card2])

        player_card1 = choice(self.cards)
        self.cards.remove(player_card1)
        player_card2 = choice(self.cards)
        self.cards.remove(player_card2)
        self.player_hand.extend([player_card1, player_card2])

        # check for player blackjack
        if self._cards_sum(self.player_hand) == 21:
            game_desc = f"你的手牌：{self.comma_concat(self.player_hand)}\n" \
                        f"对方手牌：{self.comma_concat(self.dealer_hand)}\n"
            if self._cards_sum(self.dealer_hand) == 21:  # both got blackjack, a tie
                response = game_desc + "双方黑杰克，平局"
                return GameMessage(GameMessage.BOT_FINISH, response)

            # else win double due to blackjack
            win_amount = self.bet = int(2 * self.bet)
            self.player_win_DB_transaction()

            response = game_desc + f"黑杰克！你赢得了双倍{win_amount}\n" + \
                                   f"你的余额：{self.total_money_player}，对手余额：{self.total_money_dealer}"
            return GameMessage(GameMessage.BOT_FINISH, response)

        # dealer has ace as first (revealed) card, enter insurance phase
        elif 'A' in self.dealer_hand[0]:
            self.game_phase = self.GamePhase.INSURANCE
            response = f"你的手牌：{self.comma_concat(self.player_hand)}\n" \
                       f"对手的明牌是A，你可以选择花费{int(self.bet / 2)}保险，\n" \
                       f"可选行动：{self.comma_concat(self.PHASE_ACTIONS[self.game_phase])}"
            return GameMessage(GameMessage.BOT_SEND, response)

        # no blackjack on either side, common situation
        else:
            self.game_phase = self.GamePhase.PLAYER_ACTION
            response = f"你的手牌：{self.comma_concat(self.player_hand)}\n共计{self._cards_sum(self.player_hand)}点\n" \
                       f"对手的明牌是{self.dealer_hand[0]}\n" \
                       f"可选行动：{self.comma_concat(self.PHASE_ACTIONS[self.game_phase])}"
            return GameMessage(GameMessage.BOT_SEND, response)

    def receive_input(self, player_input: str):
        """
        Handles all player inputs, cleans and validates the received input and respond accordingly
        THIS WILL BE CALLED FROM THE MAIN GAME LOOP, SO USE BOT_REJECT AND BOT_FINISH ONLY
        """
        player_input = player_input.strip()

        # invalid input
        if player_input not in self.PHASE_ACTIONS[self.game_phase]:
            return GameMessage(GameMessage.BOT_REJECT, "请从可选行动中选择一项")

        common_response = "你的手牌：{0}\n共计{1}点\n" \
                          "对手的手牌：{2}\n" \
                          "可选行动：{3}"

        bust_response = "你的手牌：{0}\n共计{1}点，爆了\n" \
                        "对手的手牌：{2}\n共计{3}点\n" \
                        "输了${4}，你的余额：{5}，对手余额：{6}"

        # handle input for common case
        if self.game_phase == self.GamePhase.PLAYER_ACTION:
            if player_input == "要牌":
                new_card = choice(self.cards)
                self.cards.remove(new_card)
                self.player_hand.append(new_card)
                # check for player bust
                curr_sum = self._cards_sum(self.player_hand)
                if curr_sum <= 21:  # player not bust
                    response = common_response.format(self.comma_concat(self.player_hand), curr_sum,
                                                      self.dealer_hand[0],
                                                      self.comma_concat(self.PHASE_ACTIONS[self.game_phase])
                                                      )
                    return GameMessage(GameMessage.BOT_REJECT, response)
                else:  # player bust
                    self.dealer_win_DB_transaction()

                    response = bust_response.format(self.comma_concat(self.player_hand), curr_sum,
                                                    self.comma_concat(self.dealer_hand), self._cards_sum(self.dealer_hand),
                                                    self.bet, self.total_money_player, self.total_money_dealer
                                                    )
                    return GameMessage(GameMessage.BOT_FINISH, response)

            elif player_input == "双倍":
                # the bet amount is doubled
                self.bet *= 2
                new_card = choice(self.cards)
                self.cards.remove(new_card)
                self.player_hand.append(new_card)
                curr_sum = self._cards_sum(self.player_hand)
                if curr_sum <= 21:  # player not bust, dealer's turn to hit
                    return self._dealer_action(curr_sum)

                else:  # player bust
                    self.dealer_win_DB_transaction()

                    response = bust_response.format(self.comma_concat(self.player_hand), curr_sum,
                                                    self.comma_concat(self.dealer_hand), self._cards_sum(self.dealer_hand),
                                                    self.bet, self.total_money_player, self.total_money_dealer
                                                    )
                    return GameMessage(GameMessage.BOT_FINISH, response)

            elif player_input == "停牌":
                curr_sum = self._cards_sum(self.player_hand)
                # dealer's turn to hit
                return self._dealer_action(curr_sum)
            else:
                raise RuntimeError('should never have occurred, maybe mismatch of input handling and possible actions')

        # handle input for insurance case
        elif self.game_phase == self.GamePhase.INSURANCE:
            if player_input == "是":
                # check for dealer blackjack
                if self._cards_sum(self.dealer_hand) == 21:  # dealer has blackjack
                    # dealer has blackjack, player wins bet amount
                    self.player_win_DB_transaction()
                    response = f"对手有黑杰克！\n对手手牌：{self.comma_concat(self.dealer_hand)}\n" \
                               f"赢了{self.bet}，你的余额：{self.total_money_player}，对手余额：{self.total_money_dealer}"
                    return GameMessage(GameMessage.BOT_FINISH, response)
                else:  # dealer no blackjack, loses insurance (half of bet)
                    self.game_phase = self.GamePhase.PLAYER_ACTION
                    insurance = int(self.bet / 2)
                    self.total_money_player = DB.get_money(self.player_qq)
                    self.total_money_dealer = DB.get_money(self.dealer_qq)
                    self.total_money_player -= insurance
                    self.total_money_dealer += insurance
                    DB.set_money(self.player_qq, self.total_money_player)
                    DB.set_money(self.dealer_qq, self.total_money_dealer)
                    insurance_info = f"对手没有黑杰克，{insurance}白给了\n"
                    response = common_response.format(self.comma_concat(self.player_hand), self._cards_sum(self.player_hand),
                                                      self.dealer_hand[0],
                                                      self.comma_concat(self.PHASE_ACTIONS[self.game_phase])
                                                      )
                    return GameMessage(GameMessage.BOT_REJECT, insurance_info + response)
            elif player_input == "否":
                self.game_phase = self.GamePhase.PLAYER_ACTION
                response = common_response.format(self.comma_concat(self.player_hand), self._cards_sum(self.player_hand),
                                                  self.dealer_hand[0],
                                                  self.comma_concat(self.PHASE_ACTIONS[self.game_phase])
                                                  )
                return GameMessage(GameMessage.BOT_REJECT, response)
            else:
                raise RuntimeError('should never have occurred, maybe mismatch of input handling and possible actions')
        else:
            raise RuntimeError('should never have occurred, unknown game phase ' + str(self.game_phase))

    def _dealer_action(self, player_sum) -> GameMessage:
        """Player has finished action, the dealer now draws card to either beat the player, or bust"""

        dealer_bust_response = "你的手牌：{0}\n共计{1}点\n" \
                               "对手的手牌：{2}\n共计{3}点，爆了\n" \
                               "赢了{4}，你的余额：{5}，对手余额：{6}"

        dealer_win_response = "你的手牌：{0}\n共计{1}点\n" \
                              "对手的手牌：{2}\n共计{3}点\n" \
                              "输了{4}，你的余额：{5}，对手余额：{6}"

        tie_response = "你的手牌：{0}\n共计{1}点\n" \
                       "对手的手牌：{2}\n共计{3}点\n" \
                       "平局，你的余额：{4}，对手余额：{5}"

        charlie_rule_response = "你的手牌：{0}\n" \
                                "对手的手牌：{1}\n共计{2}点" \
                                "五小龙直接获胜，赢了双倍{3}，你的余额：{4}，对手余额：{5}"

        # 5-card Charlie rule here, i.e. player wins with 5 cards not bust, unless dealer has blackjack
        if len(self.player_hand) >= 5:
            dealer_sum = self._cards_sum(self.dealer_hand)
            if dealer_sum != 21:  # dealer no blackjack
                # player wins double automatically, since the precondition is player not bust
                self.bet *= 2
                self.player_win_DB_transaction()
                response = charlie_rule_response.format(self.comma_concat(self.player_hand), self.comma_concat(self.dealer_hand), dealer_sum, self.bet, self.total_money_player, self.total_money_dealer)
                return GameMessage(GameMessage.BOT_FINISH, response)
            else:  # dealer has blackjack, which is better (the best actually)
                self.dealer_win_DB_transaction()
                response = dealer_win_response.format(self.comma_concat(self.player_hand), player_sum, self.comma_concat(self.dealer_hand), dealer_sum,
                                                      self.bet, self.total_money_player, self.total_money_dealer)
                explanation = "对手有黑杰克，大于你的五小龙\n"
                return GameMessage(GameMessage.BOT_FINISH, explanation + response)

        dealer_sum, drawn_cards = self._dealer_hit(player_sum)  # dealer draw cards
        if dealer_sum > 21:  # dealer bust
            self.player_win_DB_transaction()

            dealer_drawn = f"对手摸牌：{self.comma_concat(drawn_cards)}\n"
            response = dealer_bust_response.format(self.comma_concat(self.player_hand), player_sum,
                                                   self.comma_concat(self.dealer_hand), dealer_sum,
                                                   self.bet, self.total_money_player, self.total_money_dealer
                                                   )
            return GameMessage(GameMessage.BOT_FINISH, dealer_drawn + response)

        elif dealer_sum == player_sum:
            # a draw, i.e. both got 21 or dealer chose to accept a tie
            dealer_drawn = f"对手摸牌：{self.comma_concat(drawn_cards)}\n"
            response = tie_response.format(self.comma_concat(self.player_hand), player_sum,
                                           self.comma_concat(self.dealer_hand), dealer_sum,
                                           self.total_money_player, self.total_money_dealer
                                           )
            return GameMessage(GameMessage.BOT_FINISH, dealer_drawn + response)

        else:  # both not bust and not a tie, dealer must have higher sum as an invariant of `_dealer_hit()`
            self.dealer_win_DB_transaction()

            dealer_drawn = f"对手摸牌：{self.comma_concat(drawn_cards)}\n"
            response = dealer_win_response.format(self.comma_concat(self.player_hand), player_sum,
                                                  self.comma_concat(self.dealer_hand), dealer_sum,
                                                  self.bet, self.total_money_player, self.total_money_dealer
                                                  )
            return GameMessage(GameMessage.BOT_FINISH, dealer_drawn + response)

    def _dealer_hit(self, player_hand_sum) -> Tuple[int, List[str]]:
        """
        Dealer performs hits in order to beat the player's hand, or gets exactly 21,
        has the side effect of adding card to dealer_hand
        :return the final sum of dealer's hand, and the list of cards drawn
        """

        dealer_hand_sum = self._cards_sum(self.dealer_hand)
        drawn_cards = []

        def draw_a_card():
            new_card = choice(self.cards)
            drawn_cards.append(new_card)
            self.cards.remove(new_card)
            self.dealer_hand.append(new_card)

        # even if it's going to be a draw with the player also having 21, no need to draw anymore
        if dealer_hand_sum > player_hand_sum or dealer_hand_sum == 21:
            # no need to draw any card
            return dealer_hand_sum, []
        else:
            while dealer_hand_sum <= player_hand_sum:
                # dealer can choose, rather randomly, to accept a tie
                if dealer_hand_sum == player_hand_sum:
                    # stop at 21, this is the both 21 draw scenario
                    if dealer_hand_sum == 21:
                        return dealer_hand_sum, drawn_cards

                    # otherwise, some randomness here
                    chance = random()
                    accept_tie = False
                    if dealer_hand_sum < 16:
                        # most definitely hit
                        if chance < 0.8:
                            draw_a_card()
                        else:
                            accept_tie = True
                    elif dealer_hand_sum <= 18:
                        if chance < 0.5:
                            draw_a_card()
                        else:
                            accept_tie = True
                    else:
                        if chance < 0.2:
                            draw_a_card()
                        else:
                            accept_tie = True
                    if accept_tie:
                        return dealer_hand_sum, drawn_cards
                else:  # dealer's hand strictly less than player's, draw a card
                    draw_a_card()
                # must have drawn a card here, calc new dealer_hand_sum
                dealer_hand_sum = self._cards_sum(self.dealer_hand)
            return dealer_hand_sum, drawn_cards

    def player_win_DB_transaction(self):
        self.total_money_player = DB.get_money(self.player_qq)
        self.total_money_dealer = DB.get_money(self.dealer_qq)
        self.total_money_player += self.bet
        self.total_money_dealer -= self.bet
        DB.set_money(self.player_qq, self.total_money_player)
        DB.set_money(self.dealer_qq, self.total_money_dealer)

    def dealer_win_DB_transaction(self):
        self.total_money_player = DB.get_money(self.player_qq)
        self.total_money_dealer = DB.get_money(self.dealer_qq)
        self.total_money_player -= self.bet
        self.total_money_dealer += self.bet
        DB.set_money(self.player_qq, self.total_money_player)
        DB.set_money(self.dealer_qq, self.total_money_dealer)