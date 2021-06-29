from typing import List, Dict, Tuple
from itertools import product
from random import choice
import re
from enum import Enum
from .database import DB

NEW_PLAYER_MONEY = 500


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
    player_total: int = 0
    dealer_hand: List[str] = []
    dealer_total: int = 0

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

        self.bet, self.player_qq, self.dealer_qq = bet, player_qq, dealer_qq

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
                assert 2 <= rank <= 10  # TODO
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
            game_desc = f"赌注：${self.bet}\n" + f"你的手牌：{self.comma_concat(self.player_hand)}\n" \
                                              f"对方手牌：{self.comma_concat(self.dealer_hand)}\n"
            if self._cards_sum(self.dealer_hand) == 21:  # both got blackjack, a tie
                response = game_desc + "双方黑杰克，平局"
                return GameMessage(GameMessage.BOT_FINISH, response)

            # else win double due to blackjack
            win_amount = int(2 * self.bet)

            # handle winning money and db here
            self.total_money_player += win_amount
            self.total_money_dealer -= win_amount
            DB.set_money(self.player_qq, self.total_money_player)
            DB.set_money(self.dealer_qq, self.total_money_dealer)

            response = game_desc + f"黑杰克！你赢得了双倍赌注{win_amount}\n" + \
                                   f"你的余额：{self.total_money_player}，对手余额：{self.total_money_dealer}"
            return GameMessage(GameMessage.BOT_FINISH, response)

        # dealer has ace as first (revealed) card, enter insurance phase
        elif 'A' in self.dealer_hand[0]:
            self.game_phase = self.GamePhase.INSURANCE
            response = f"赌注：${self.bet}\n" \
                       f"你的手牌：{self.comma_concat(self.player_hand)}\n" \
                       f"庄家的明牌是A，你可以选择花费${int(self.bet / 2)}买保险，\n" \
                       f"可选行动：{self.comma_concat(self.PHASE_ACTIONS[self.game_phase])}"
            return GameMessage(GameMessage.BOT_SEND, response)

        # no blackjack on either side, common situation
        else:
            self.game_phase = self.GamePhase.PLAYER_ACTION
            response = f"赌注：${self.bet}\n" \
                       f"你的手牌：{self.comma_concat(self.player_hand)}\n共计{self._cards_sum(self.player_hand)}点\n" \
                       f"庄家的明牌是{self.dealer_hand[0]}\n" \
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

        total_money_player, total_money_dealer = self.total_money_player, self.total_money_dealer

        common_response = "你的手牌：{0}\n共计{1}点\n" \
                          "庄家的手牌：{2}\n" \
                          "可选行动：{3}"

        bust_response = "你的手牌：{0}\n共计{1}点，爆了\n" \
                        "庄家的手牌：{2}\n共计{3}点\n" \
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
                    total_money_player -= self.bet
                    total_money_dealer += self.bet
                    DB.set_money(self.player_qq, total_money_player)
                    DB.set_money(self.dealer_qq, total_money_dealer)

                    response = bust_response.format(self.comma_concat(self.player_hand), curr_sum,
                                                    self.dealer_hand[0], self._cards_sum(self.dealer_hand),
                                                    self.bet, total_money_player, total_money_dealer
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
                    total_money_player -= self.bet
                    total_money_dealer += self.bet
                    DB.set_money(self.player_qq, total_money_player)
                    DB.set_money(self.dealer_qq, total_money_dealer)

                    response = bust_response.format(self.comma_concat(self.player_hand), curr_sum,
                                                    self.comma_concat(self.dealer_hand), self._cards_sum(self.dealer_hand),
                                                    self.bet, total_money_player, total_money_dealer
                                                    )
                    return GameMessage(GameMessage.BOT_FINISH, response)

            elif player_input == "停牌":
                curr_sum = self._cards_sum(self.player_hand)
                # dealer's turn to hit
                return self._dealer_action(curr_sum)
            else:
                raise RuntimeError('should never have occurred, maybe mismatch of input handling and possible actions')

        # handle input for insurance case
        elif self.GamePhase == self.GamePhase.INSURANCE:
            if player_input == "是":
                # check for dealer blackjack
                if self._cards_sum(self.dealer_hand) == 21:  # dealer has blackjack
                    # dealer has blackjack, player wins bet amount
                    self.total_money_player += self.bet
                    self.total_money_dealer -= self.bet
                    DB.set_money(self.player_qq, self.total_money_player)
                    DB.set_money(self.dealer_qq, self.total_money_dealer)
                    response = f"庄家有黑杰克！\n庄家手牌：{self.comma_concat(self.dealer_hand)}\n" \
                               f"赢了${self.bet}，你的余额：{self.total_money_player}，对手余额：{self.total_money_dealer}"
                    return GameMessage(GameMessage.BOT_FINISH, response)
                else:  # dealer no blackjack, loses insurance (half of bet)
                    self.game_phase = self.GamePhase.PLAYER_ACTION
                    insurance = int(self.bet / 2)
                    self.total_money_player -= insurance
                    self.total_money_dealer += insurance
                    # no need to do DB transactions here, not end game yet
                    response = f"庄家没有黑杰克，${insurance}保险金白给了"
                    return GameMessage(GameMessage.BOT_REJECT, response)
            elif player_input == "否":
                self.game_phase = self.GamePhase.PLAYER_ACTION
                response = common_response.format(self.comma_concat(self.player_hand), self._cards_sum(self.player_hand),
                                                  self.dealer_hand[0],
                                                  self.comma_concat(self.PHASE_ACTIONS[self.game_phase])
                                                  )
            else:
                raise RuntimeError('should never have occurred, maybe mismatch of input handling and possible actions')

    def _dealer_action(self, player_sum) -> GameMessage:
        """Player has finished action, the dealer now draws card to either beat the player, or bust"""

        dealer_bust_response = "你的手牌：{0}\n共计{1}点\n" \
                               "庄家的手牌：{2}\n共计{3}点，爆了\n" \
                               "赢了${4}，你的余额：{5}，对手余额：{6}"

        dealer_win_response = "你的手牌：{0}\n共计{1}点\n" \
                              "庄家的手牌：{2}\n共计{3}点\n" \
                              "输了${4}，你的余额：{5}，对手余额：{6}"

        dealer_sum, drawn_cards = self._dealer_hit()
        if dealer_sum > 21:  # dealer bust
            self.total_money_player += self.bet
            self.total_money_dealer -= self.bet
            DB.set_money(self.player_qq, self.total_money_player)
            DB.set_money(self.dealer_qq, self.total_money_dealer)

            dealer_drawn = f"庄家摸牌：{self.comma_concat(drawn_cards)}\n"
            response = dealer_bust_response.format(self.comma_concat(self.player_hand), player_sum,
                                                   self.comma_concat(self.dealer_hand), dealer_sum,
                                                   self.bet, self.total_money_player, self.total_money_dealer
                                                   )
            return GameMessage(GameMessage.BOT_FINISH, dealer_drawn + response)
        else:  # both not bust, dealer must have higher sum as an invariant of `_dealer_hit()`
            self.total_money_player -= self.bet
            self.total_money_dealer += self.bet
            DB.set_money(self.player_qq, self.total_money_player)
            DB.set_money(self.dealer_qq, self.total_money_dealer)

            dealer_drawn = f"庄家摸牌：{self.comma_concat(drawn_cards)}\n"
            response = dealer_win_response.format(self.comma_concat(self.player_hand), player_sum,
                                                  self.comma_concat(self.dealer_hand), dealer_sum,
                                                  self.bet, self.total_money_player, self.total_money_dealer
                                                  )
            return GameMessage(GameMessage.BOT_FINISH, dealer_drawn + response)

    def get_player_actions_list(self) -> List[str]:
        """returns a list of Chinese strings representing available actions"""
        pass

    def _dealer_hit(self) -> Tuple[int, List[str]]:
        """
        Dealer performs hits in order to beat the player's hand, has the side effect of adding card to dealer_hand
        :return the final sum of dealer's hand, and the list of cards drawn
        """
        player_hand_sum = self._cards_sum(self.player_hand)
        dealer_hand_sum = self._cards_sum(self.dealer_hand)

        if dealer_hand_sum > player_hand_sum:
            # no need to draw any card
            return dealer_hand_sum, []
        else:
            drawn_cards = []
            while dealer_hand_sum <= player_hand_sum:
                new_card = choice(self.cards)
                drawn_cards.append(new_card)
                self.cards.remove(new_card)
                self.dealer_hand.append(new_card)
                dealer_hand_sum = self._cards_sum(self.dealer_hand)
            return dealer_hand_sum, drawn_cards
